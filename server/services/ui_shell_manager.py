import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import time
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Protocol

from .agent_cli_manager import AgentCliManager
from .run_folder_trust_manager import run_folder_trust_manager


class UiShellBusyError(RuntimeError):
    pass


class UiShellValidationError(ValueError):
    pass


class UiShellRuntimeError(RuntimeError):
    pass


TERMINAL_STATES = {"exited", "error", "timeout", "terminated"}
logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class CommandSpec:
    id: str
    label: str
    engine: str
    args: tuple[str, ...]


class TrustManagerProtocol(Protocol):
    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        ...

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        ...

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        ...


class UiShellSession:
    def __init__(
        self,
        session_id: str,
        command: CommandSpec,
        process: subprocess.Popen[Any],
        cwd: Path,
        trust_engine: str,
        ttyd_bind_host: str,
        ttyd_port: int,
        hard_ttl_sec: int,
        sandbox_status: str = "unknown",
        sandbox_message: str = "",
    ) -> None:
        self.id = session_id
        self.command = command
        self.trust_engine = trust_engine
        self.cwd = str(cwd)
        self.cwd_path = cwd
        self.pid = int(process.pid)
        self.ttyd_bind_host = ttyd_bind_host
        self.ttyd_port = int(ttyd_port)
        self.hard_ttl_sec = int(hard_ttl_sec)
        self.created_at = _utc_iso()
        self.updated_at = self.created_at
        self._start_wall_epoch = time.time()
        self.status = "running"
        self.exit_code: Optional[int] = None
        self.error: Optional[str] = None
        self.sandbox_status = sandbox_status
        self.sandbox_message = sandbox_message
        self._lock = Lock()
        self._start_monotonic = time.monotonic()
        self._process = process

    def _mark_terminal(
        self,
        status: str,
        *,
        exit_code: Optional[int],
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if self.status in TERMINAL_STATES:
                return
            self.status = status
            self.exit_code = exit_code
            self.error = error
            self.updated_at = _utc_iso()

    def _refresh_status(self) -> None:
        if self.status in TERMINAL_STATES:
            return
        if (time.monotonic() - self._start_monotonic) > self.hard_ttl_sec:
            self.terminate(
                reason="timeout",
                message=f"Hard TTL exceeded ({self.hard_ttl_sec}s)",
            )
            return
        code = self._process.poll()
        if code is not None:
            self._mark_terminal("exited", exit_code=code)

    def terminate(self, reason: str = "terminated", message: Optional[str] = None) -> None:
        self._refresh_status()
        if self.status in TERMINAL_STATES:
            return

        try:
            if platform.system().lower().startswith("win"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                os.killpg(self.pid, signal.SIGTERM)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if self._process.poll() is not None:
                        break
                    time.sleep(0.1)
                if self._process.poll() is None:
                    os.killpg(self.pid, signal.SIGKILL)
        except Exception:
            pass

        code = self._process.poll()
        self._mark_terminal(reason, exit_code=code, error=message)

    def snapshot(self) -> Dict[str, Any]:
        self._refresh_status()
        expires_at = datetime.fromtimestamp(
            self._start_wall_epoch + self.hard_ttl_sec, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            return {
                "session_id": self.id,
                "command_id": self.command.id,
                "command_label": self.command.label,
                "engine": self.command.engine,
                "cwd": self.cwd,
                "pid": self.pid,
                "status": self.status,
                "exit_code": self.exit_code,
                "error": self.error,
                "sandbox_status": self.sandbox_status,
                "sandbox_message": self.sandbox_message,
                "ttyd_bind_host": self.ttyd_bind_host,
                "ttyd_port": self.ttyd_port,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "expires_at": expires_at,
                "hard_ttl_sec": self.hard_ttl_sec,
                "terminal": self.status in TERMINAL_STATES,
            }


class UiShellManager:
    def __init__(
        self,
        agent_manager: Optional[AgentCliManager] = None,
        trust_manager: Optional[TrustManagerProtocol] = None,
    ) -> None:
        self.agent_manager = agent_manager or AgentCliManager()
        self.trust_manager = trust_manager or run_folder_trust_manager
        self._lock = Lock()
        self._active_session: Optional[UiShellSession] = None
        self._command_specs: Dict[str, CommandSpec] = {
            "codex": CommandSpec(
                "codex-tui",
                "Codex TUI",
                "codex",
                (
                    "--sandbox",
                    "workspace-write",
                    "--ask-for-approval",
                    "never",
                    "-c",
                    "features.shell_tool=false",
                    "-c",
                    "features.unified_exec=false",
                ),
            ),
            "gemini": CommandSpec(
                "gemini-tui",
                "Gemini TUI",
                "gemini",
                (
                    "--sandbox",
                    "--approval-mode",
                    "default",
                ),
            ),
            "iflow": CommandSpec(
                "iflow-tui",
                "iFlow TUI",
                "iflow",
                (),
            ),
        }

    def list_commands(self) -> list[Dict[str, str]]:
        return [
            {"id": item.id, "label": item.label, "engine": item.engine}
            for item in self._command_specs.values()
        ]

    def _get_hard_ttl(self) -> int:
        value = int(os.environ.get("UI_SHELL_HARD_TTL_SECONDS", "1800"))
        return max(60, value)

    def _session_root(self) -> Path:
        return self.agent_manager.profile.data_dir / "ui_shell_sessions"

    def _ttyd_bind_host(self) -> str:
        return os.environ.get("UI_SHELL_TTYD_BIND_HOST", "0.0.0.0").strip() or "0.0.0.0"

    def _ttyd_port(self) -> int:
        value = int(os.environ.get("UI_SHELL_TTYD_PORT", "7681"))
        if value <= 0 or value > 65535:
            raise UiShellRuntimeError("UI_SHELL_TTYD_PORT must be in 1..65535")
        return value

    def _is_port_available(self, host: str, port: int) -> bool:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def _pick_ttyd_port(self, host: str) -> int:
        base_port = self._ttyd_port()
        if self._is_port_available(host, base_port):
            return base_port

        runtime_mode = str(getattr(self.agent_manager.profile, "mode", "local")).lower()
        if runtime_mode == "local":
            upper = min(base_port + 30, 65535)
            for candidate in range(base_port + 1, upper + 1):
                if self._is_port_available(host, candidate):
                    return candidate

        raise UiShellBusyError(
            f"ttyd port {base_port} is already in use; set UI_SHELL_TTYD_PORT to another value."
        )

    def _probe_sandbox_status(self, engine: str) -> tuple[str, str]:
        if engine == "codex":
            if os.environ.get("LANDLOCK_ENABLED") == "0":
                return (
                    "unsupported",
                    "LANDLOCK is disabled in current environment; codex inline TUI runs without enforced sandbox.",
                )
            return ("supported", "LANDLOCK enabled.")
        if engine == "gemini":
            env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
            path_env = env.get("PATH", os.environ.get("PATH", ""))
            runtime_errors: list[str] = []
            for runtime in ("docker", "podman"):
                runtime_path = shutil.which(runtime, path=path_env)
                if not runtime_path:
                    continue
                try:
                    result = subprocess.run(
                        [runtime_path, "info"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=3,
                    )
                except Exception as exc:
                    runtime_errors.append(f"{runtime}: {str(exc)}")
                    continue
                if result.returncode == 0:
                    return (
                        "supported",
                        f"{engine} sandbox runtime is available via {runtime}.",
                    )
                first_line = ((result.stderr or "").strip() or (result.stdout or "").strip()).splitlines()
                detail = first_line[0] if first_line else f"exit={result.returncode}"
                runtime_errors.append(f"{runtime}: {detail}")
            if runtime_errors:
                return (
                    "unsupported",
                    f"{engine} sandbox runtime is unavailable ({'; '.join(runtime_errors)}).",
                )
            return (
                "unsupported",
                "gemini sandbox runtime is unavailable (docker/podman not found).",
            )
        if engine == "iflow":
            return (
                "unsupported",
                "iFlow inline TUI runs without sandbox. iFlow sandbox requires Docker-image execution, "
                "which is intentionally outside this inline TUI design.",
            )
        return ("unknown", "Sandbox capability is unknown for this engine.")

    def _cleanup_stale_session_locked(self) -> None:
        if self._active_session is None:
            return
        session = self._active_session
        state = session.snapshot()
        if state.get("terminal"):
            self._cleanup_trust_for_session(session)
            self._active_session = None
            return
        raise UiShellBusyError("Another inline TUI session is already running")

    def _inject_trust_for_session(self, engine: str, session_dir: Path) -> None:
        if engine in {"codex", "gemini"}:
            # Keep the session parent trusted so CLI startup does not ask trust interactively.
            self.trust_manager.bootstrap_parent_trust(self._session_root())
        self.trust_manager.register_run_folder(engine, session_dir)

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _prepare_session_security(
        self,
        engine: str,
        session_dir: Path,
        env: Dict[str, str],
        *,
        sandbox_enabled: bool,
    ) -> None:
        # TUI session security is intentionally isolated from RUN-path adapter policies.
        if engine == "gemini":
            self._write_json(
                session_dir / ".gemini" / "settings.json",
                {
                    "tools": {
                        "sandbox": sandbox_enabled,
                        "autoAccept": False,
                        "exclude": ["run_shell_command", "ShellTool"],
                    },
                    "security": {
                        "disableYoloMode": True,
                    },
                },
            )
            return
        if engine == "iflow":
            self._write_json(
                session_dir / ".iflow" / "settings.json",
                {
                    "sandbox": False,
                    "autoAccept": False,
                    "approvalMode": "default",
                    "excludeTools": ["ShellTool"],
                },
            )
            return

    def _cleanup_trust_for_session(self, session: UiShellSession) -> None:
        try:
            self.trust_manager.remove_run_folder(session.trust_engine, session.cwd_path)
        except Exception:
            logger.warning(
                "Failed to cleanup UI TUI trust entry for engine=%s session_id=%s",
                session.trust_engine,
                    session.id,
                    exc_info=True,
                )

    def _spawn_ttyd_process(
        self,
        *,
        ttyd_path: Path,
        ttyd_host: str,
        ttyd_port: int,
        session_dir: Path,
        command_path: Path,
        launch_args: list[str],
        env: Dict[str, str],
    ) -> subprocess.Popen[Any]:
        return subprocess.Popen(
            [
                str(ttyd_path),
                "--writable",
                "-i",
                ttyd_host,
                "-p",
                str(ttyd_port),
                "-w",
                str(session_dir),
                "--",
                str(command_path),
                *launch_args,
            ],
            cwd=str(session_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=False,
            start_new_session=True,
            close_fds=True,
        )

    def get_session_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            session = self._active_session
        if session is None:
            return {"active": False}
        data = session.snapshot()
        data["active"] = True
        if data.get("terminal"):
            with self._lock:
                if self._active_session is session:
                    self._cleanup_trust_for_session(session)
                    self._active_session = None
        return data

    def start_session(self, engine: str) -> Dict[str, Any]:
        normalized_engine = engine.strip().lower()
        spec = self._command_specs.get(normalized_engine)
        if spec is None:
            raise UiShellValidationError(f"Unsupported engine: {engine}")

        with self._lock:
            self._cleanup_stale_session_locked()
            command_path = self.agent_manager.resolve_engine_command(spec.engine)
            if command_path is None:
                raise UiShellRuntimeError(f"Engine CLI not found for: {spec.engine}")
            ttyd_path = self.agent_manager.resolve_ttyd_command()
            if ttyd_path is None:
                raise UiShellRuntimeError(
                    "ttyd not found. Install ttyd first (required for inline TUI)."
                )

            sandbox_status, sandbox_message = self._probe_sandbox_status(spec.engine)
            sandbox_enabled = sandbox_status == "supported"
            session_id = str(uuid.uuid4())
            session_dir = self._session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            ttyd_host = self._ttyd_bind_host()
            ttyd_port = self._pick_ttyd_port(ttyd_host)
            trust_registered = False

            try:
                self._inject_trust_for_session(spec.engine, session_dir)
                trust_registered = True

                env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
                env["SKILL_RUNNER_UI_SHELL_SESSION_DIR"] = str(session_dir)
                env["SKILL_RUNNER_UI_SHELL_ALLOWED_WRITE_ROOTS"] = os.pathsep.join(
                    [str(session_dir), str(self.agent_manager.profile.agent_home)]
                )
                env.setdefault("TERM", "xterm-256color")
                env.setdefault("COLORTERM", "truecolor")
                # Avoid inheriting externally-forced sandbox env flags that can break CLI startup.
                env.pop("GEMINI_SANDBOX", None)
                env.pop("IFLOW_SANDBOX", None)
                self._prepare_session_security(
                    spec.engine,
                    session_dir,
                    env,
                    sandbox_enabled=sandbox_enabled,
                )
                launch_args = list(spec.args)
                if spec.engine == "gemini" and not sandbox_enabled:
                    launch_args = [item for item in launch_args if item != "--sandbox"]

                process = self._spawn_ttyd_process(
                    ttyd_path=ttyd_path,
                    ttyd_host=ttyd_host,
                    ttyd_port=ttyd_port,
                    session_dir=session_dir,
                    command_path=command_path,
                    launch_args=launch_args,
                    env=env,
                )

                if spec.engine == "gemini" and "--sandbox" in launch_args:
                    # In non-fail-closed mode, if sandbox launch exits immediately, retry once without sandbox.
                    time.sleep(0.4)
                    first_exit_code = process.poll()
                    if first_exit_code is not None:
                        retry_args = [item for item in launch_args if item != "--sandbox"]
                        process = self._spawn_ttyd_process(
                            ttyd_path=ttyd_path,
                            ttyd_host=ttyd_host,
                            ttyd_port=ttyd_port,
                            session_dir=session_dir,
                            command_path=command_path,
                            launch_args=retry_args,
                            env=env,
                        )
                        sandbox_status = "unsupported"
                        sandbox_message = (
                            f"{spec.engine} sandbox launch exited early (code {first_exit_code}); "
                            "retried without --sandbox."
                        )
            except Exception:
                if trust_registered:
                    try:
                        self.trust_manager.remove_run_folder(spec.engine, session_dir)
                    except Exception:
                        logger.warning(
                            "Failed to rollback UI TUI trust entry for engine=%s session_dir=%s",
                            spec.engine,
                            session_dir,
                            exc_info=True,
                        )
                raise

            session = UiShellSession(
                session_id=session_id,
                command=spec,
                process=process,
                cwd=session_dir,
                trust_engine=spec.engine,
                ttyd_bind_host=ttyd_host,
                ttyd_port=ttyd_port,
                hard_ttl_sec=self._get_hard_ttl(),
                sandbox_status=sandbox_status,
                sandbox_message=sandbox_message,
            )
            self._active_session = session

            data = session.snapshot()
            data["active"] = True
            data["session_dir"] = str(session_dir)
            data["agent_home"] = str(self.agent_manager.profile.agent_home)
            return data

    def stop_session(self) -> Dict[str, Any]:
        with self._lock:
            session = self._active_session
        if session is None:
            return {"active": False}
        session.terminate(reason="terminated", message="Stopped by user")
        data = session.snapshot()
        data["active"] = True
        with self._lock:
            if self._active_session is session:
                self._cleanup_trust_for_session(session)
                self._active_session = None
        return data


ui_shell_manager = UiShellManager()
