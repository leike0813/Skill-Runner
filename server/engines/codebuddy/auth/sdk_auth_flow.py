from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

from server.engines.codebuddy.auth.credential_store import (
    CodeBuddyCredentialStore,
    codebuddy_credential_store,
)
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.services.platform.process_termination import terminate_popen_process_tree


_WORKER_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:auth_?token|api_?key|token)\s*[:=]\s*)[^\s,;]+"),
)
logger = logging.getLogger(__name__)


@dataclass
class CodeBuddySdkAuthSession:
    provider_id: str
    process: subprocess.Popen[str]
    temp_root: Path
    messages: queue.Queue[dict[str, Any]]
    stderr_chunks: list[str] = field(default_factory=list)
    auth_url: str = ""
    completed: bool = False
    cleaned: bool = False


class CodeBuddySdkAuthFlow:
    def __init__(
        self,
        *,
        credential_store: CodeBuddyCredentialStore | None = None,
        on_success: Callable[[str], None] | None = None,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.credential_store = credential_store or codebuddy_credential_store
        self.on_success = on_success
        self._popen_factory = popen_factory

    def start(
        self,
        *,
        provider_id: str,
        codebuddy_path: Path,
        timeout: float,
        startup_timeout: float = 30.0,
    ) -> CodeBuddySdkAuthSession:
        provider = require_provider(provider_id)
        temp_root = Path(tempfile.mkdtemp(prefix=f"codebuddy-auth-{provider.provider_id}-"))
        self._prepare_temp_root(temp_root)
        env = self.build_worker_environment(temp_root)
        worker_path = Path(__file__).with_name("sdk_worker.py")
        command = [
            sys.executable,
            str(worker_path),
            "--environment",
            provider.sdk_environment,
            "--codebuddy-path",
            str(codebuddy_path),
            "--timeout",
            str(max(1.0, float(timeout))),
            "--temp-root",
            str(temp_root),
        ]
        try:
            process = self._popen_factory(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=temp_root,
                start_new_session=os.name != "nt",
            )
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise
        messages: queue.Queue[dict[str, Any]] = queue.Queue()
        session = CodeBuddySdkAuthSession(
            provider_id=provider.provider_id,
            process=process,
            temp_root=temp_root,
            messages=messages,
        )
        self._start_reader(process.stdout, messages)
        self._start_stderr_reader(process.stderr, session.stderr_chunks)
        try:
            first = messages.get(timeout=max(0.1, startup_timeout))
        except queue.Empty as exc:
            self.cancel(session)
            raise TimeoutError("CodeBuddy SDK did not return an auth URL") from exc
        if first.get("type") == "error":
            error = self._redact(str(first.get("error") or "CodeBuddy SDK auth failed"))
            self.cancel(session)
            raise RuntimeError(error)
        if first.get("type") != "auth_url":
            self.cancel(session)
            raise RuntimeError("CodeBuddy SDK auth worker protocol is invalid")
        session.auth_url = str(first.get("auth_url") or "")
        return session

    def poll(self, session: CodeBuddySdkAuthSession) -> str:
        if session.completed:
            return "succeeded"
        while True:
            try:
                message = session.messages.get_nowait()
            except queue.Empty:
                break
            message_type = message.get("type")
            if message_type == "credential":
                token = str(message.get("token") or "")
                user_id = str(message.get("user_id") or "")
                self.credential_store.put(
                    session.provider_id,
                    token=token,
                    user_id=user_id,
                )
                session.completed = True
                if self.on_success is not None:
                    try:
                        self.on_success(session.provider_id)
                    except Exception:
                        logger.warning(
                            "CodeBuddy post-auth refresh failed provider_id=%s",
                            session.provider_id,
                            exc_info=True,
                        )
                self._settle_completed_worker(session)
                self._cleanup(session)
                return "succeeded"
            if message_type == "error":
                self._terminate_worker(session)
                self._cleanup(session)
                raise RuntimeError(self._redact(str(message.get("error") or "CodeBuddy SDK auth failed")))
        return_code = session.process.poll()
        if return_code is not None:
            self._cleanup(session)
            detail = self.stderr_text(session)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"CodeBuddy SDK auth worker exited with code {return_code}{suffix}")
        return "waiting_user"

    def cancel(self, session: CodeBuddySdkAuthSession) -> None:
        self._terminate_worker(session)
        self._cleanup(session)

    def stderr_text(self, session: CodeBuddySdkAuthSession) -> str:
        return self._redact("".join(session.stderr_chunks).strip())

    @staticmethod
    def build_worker_environment(temp_root: Path) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items() if key in _WORKER_ENV_ALLOWLIST}
        config_dir = temp_root / "config"
        env.update(
            {
                "HOME": str(temp_root / "home"),
                "USERPROFILE": str(temp_root / "home"),
                "XDG_CONFIG_HOME": str(temp_root / "xdg-config"),
                "XDG_DATA_HOME": str(temp_root / "xdg-data"),
                "XDG_CACHE_HOME": str(temp_root / "xdg-cache"),
                "XDG_STATE_HOME": str(temp_root / "xdg-state"),
                "CODEBUDDY_CONFIG_DIR": str(config_dir),
                "PYTHONUNBUFFERED": "1",
            }
        )
        return env

    @staticmethod
    def _prepare_temp_root(temp_root: Path) -> None:
        os.chmod(temp_root, 0o700)
        for name in ("home", "config", "xdg-config", "xdg-data", "xdg-cache", "xdg-state"):
            path = temp_root / name
            path.mkdir(mode=0o700)

    @staticmethod
    def _start_reader(
        stream: TextIO | None,
        messages: queue.Queue[dict[str, Any]],
    ) -> None:
        def _read() -> None:
            if stream is None:
                return
            for raw_line in stream:
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    messages.put({"type": "error", "error": "Invalid CodeBuddy auth worker response"})
                    continue
                if isinstance(payload, dict):
                    messages.put(payload)

        threading.Thread(target=_read, name="codebuddy-auth-stdout", daemon=True).start()

    @staticmethod
    def _start_stderr_reader(stream: TextIO | None, chunks: list[str]) -> None:
        def _read() -> None:
            if stream is None:
                return
            for chunk in stream:
                chunks.append(chunk)
                if sum(len(item) for item in chunks) > 32768:
                    del chunks[:-8]

        threading.Thread(target=_read, name="codebuddy-auth-stderr", daemon=True).start()

    @staticmethod
    def _redact(text: str) -> str:
        redacted = text
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted[:2048]

    @staticmethod
    def _terminate_worker(session: CodeBuddySdkAuthSession) -> None:
        if session.process.poll() is not None:
            return
        result = terminate_popen_process_tree(
            session.process,
            term_grace_sec=1,
            kill_grace_sec=1,
        )
        if result.outcome == "failed" and session.process.poll() is None:
            session.process.kill()
            session.process.wait(timeout=3)

    @classmethod
    def _settle_completed_worker(cls, session: CodeBuddySdkAuthSession) -> None:
        try:
            session.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            cls._terminate_worker(session)

    @staticmethod
    def _cleanup(session: CodeBuddySdkAuthSession) -> None:
        if session.cleaned:
            return
        shutil.rmtree(session.temp_root, ignore_errors=True)
        session.cleaned = True
