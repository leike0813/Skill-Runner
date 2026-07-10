#!/usr/bin/env python3
"""Capture reproducible, secret-safe evidence for CodeBuddy CLI integration.

This is a forensic utility, not part of the Skill Runner runtime. By default it
only runs local CLI metadata and offline replay analysis. Agent turns require
--allow-agent-cases and either an explicit probe credential or an explicit
authorization to reuse the host credential manager.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import contextlib
import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import shutil
import signal
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ("metadata", "offline-replay")
AGENT_CASES = {
    "unauthenticated",
    "invalid-api-key",
    "explicit-credential",
    "helper-credential",
    "materialization",
    "structured-json",
    "structured-stream",
    "tool-event",
    "resume",
    "cancel",
    "concurrency",
    "sdk-auth-token",
    "sdk-interactive-auth",
    "document-sample-1",
    "document-sample-2",
    "service-config-isolation",
    "sdk-token-lifecycle",
}
CASE_CHOICES = (*DEFAULT_CASES, *sorted(AGENT_CASES))
PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
SAFE_BASE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", *PROXY_ENV_KEYS)
HOST_AUTH_ENV_KEYS = ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY")
REDACTED = "[REDACTED]"
DOCUMENT_SAMPLE_1_PROMPT = (
    "去搜索一下美国和伊朗的摩擦的最新情况，然后编写一个脚本，计算从这场摩擦开始到现在经过了多少天，"
    "然后找到这个天数的所有质因数分解结果"
)
DOCUMENT_SAMPLE_2_PROMPTS = (
    "尝试问我三个问题，然后从我的回答中推断出我的职业。**要求：每次只能问一个问题，一个一个来。**",
    "codex、vscode、zotero",
    "既有面向学术界的论文，也有面向公众的软件、教程等等，也有给公司内部团队用的产品/报告",
    "写代码、写文章、处理数据",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def redact_bytes(raw: bytes, secrets_to_redact: Iterable[str]) -> bytes:
    sanitized = raw
    for secret_value in secrets_to_redact:
        if secret_value:
            sanitized = sanitized.replace(secret_value.encode("utf-8"), REDACTED.encode("utf-8"))
    sanitized = re.sub(
        rb"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+",
        rb"\1" + REDACTED.encode("utf-8"),
        sanitized,
    )
    return sanitized


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_tree(root: Path, *, limit: int = 2_000) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if not root.exists():
        return {"root": str(root), "exists": False, "entries": entries, "truncated": False}
    for path in sorted(root.rglob("*")):
        if len(entries) >= limit:
            return {"root": str(root), "exists": True, "entries": entries, "truncated": True}
        try:
            stat = path.lstat()
        except OSError:
            continue
        entries.append(
            {
                "path": str(path.relative_to(root)),
                "kind": "symlink" if path.is_symlink() else "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "mode": oct(stat.st_mode & 0o777),
            }
        )
    return {"root": str(root), "exists": True, "entries": entries, "truncated": False}


def reframed_json_rows(text: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Recover JSON objects split by literal newlines inside quoted strings.

    CodeBuddy captures have violated JSONL by emitting physical newlines in
    string values.  This is only an evidence analyzer; it preserves neither the
    original byte offsets nor replaces the future runtime parser.
    """

    logical_rows: list[str] = []
    current: list[str] = []
    in_string = False
    escaped = False
    depth = 0
    started = False
    repaired_newlines = 0

    for char in text:
        if char in "{[" and not in_string:
            depth += 1
            started = True
        elif char in "}]" and not in_string and depth:
            depth -= 1

        if char == "\n":
            if in_string:
                current.append("\\n")
                repaired_newlines += 1
            elif started and depth == 0:
                candidate = "".join(current).strip()
                if candidate:
                    logical_rows.append(candidate)
                current = []
                started = False
            else:
                current.append(char)
            escaped = False
            continue

        current.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True

    candidate = "".join(current).strip()
    if candidate:
        logical_rows.append(candidate)

    rows: list[dict[str, Any]] = []
    parse_errors = 0
    for candidate in logical_rows:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, {
        "physical_lines": len(text.splitlines()),
        "logical_rows": len(logical_rows),
        "parsed_rows": len(rows),
        "parse_errors": parse_errors,
        "repaired_newlines": repaired_newlines,
    }


def _event_summary(rows: list[dict[str, Any]], *, framing: dict[str, Any], output_format: str) -> dict[str, Any]:
    type_counts = Counter(str(row.get("type") or "unknown") for row in rows)
    session_ids = sorted(
        {
            session_id
            for row in rows
            for session_id in (row.get("session_id"), row.get("sessionId"))
            if isinstance(session_id, str) and session_id
        }
    )
    init_rows = [row for row in rows if row.get("type") == "system" and row.get("subtype") == "init"]
    result_rows = [row for row in rows if row.get("type") == "result"]
    return {
        "output_format": output_format,
        "framing": framing,
        "types": dict(sorted(type_counts.items())),
        "session_ids": session_ids,
        "init_models": sorted(
            {
                model
                for row in init_rows
                if isinstance((model := row.get("model")), str) and model
            }
        ),
        "api_key_sources": sorted(
            {
                source
                for row in init_rows
                if isinstance((source := row.get("apiKeySource")), str) and source
            }
        ),
        "result_rows": [
            {
                "subtype": row.get("subtype"),
                "is_error": row.get("is_error"),
                "has_structured_output": row.get("structured_output") is not None,
            }
            for row in result_rows
        ],
    }


def protocol_summary(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, list) and all(isinstance(item, dict) for item in document):
        return _event_summary(
            document,
            framing={"physical_lines": len(text.splitlines()), "items": len(document), "parse_errors": 0, "repaired_newlines": 0},
            output_format="json_array",
        )
    if isinstance(document, dict):
        return _event_summary(
            [document],
            framing={"physical_lines": len(text.splitlines()), "items": 1, "parse_errors": 0, "repaired_newlines": 0},
            output_format="json_object",
        )
    rows, framing = reframed_json_rows(text)
    return _event_summary(rows, framing=framing, output_format="stream_json")


def sanitize_environment(
    *,
    home_dir: Path,
    config_dir: Path,
    network_environment: str | None,
    use_host_state: bool,
    credential: tuple[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    env = {key: os.environ[key] for key in SAFE_BASE_ENV_KEYS if os.environ.get(key)}
    if use_host_state:
        env["HOME"] = os.environ.get("HOME", str(Path.home()))
        env.update({key: os.environ[key] for key in HOST_AUTH_ENV_KEYS if os.environ.get(key)})
        host_config_dir = os.environ.get("CODEBUDDY_CONFIG_DIR")
        if host_config_dir:
            env["CODEBUDDY_CONFIG_DIR"] = host_config_dir
    else:
        env.update(
            {
                "HOME": str(home_dir),
                "CODEBUDDY_CONFIG_DIR": str(config_dir),
                "XDG_CONFIG_HOME": str(home_dir / ".config"),
                "XDG_DATA_HOME": str(home_dir / ".local" / "share"),
                "XDG_CACHE_HOME": str(home_dir / ".cache"),
                "XDG_STATE_HOME": str(home_dir / ".local" / "state"),
            }
        )
    if network_environment:
        env["CODEBUDDY_INTERNET_ENVIRONMENT"] = network_environment
    secrets_to_redact: list[str] = []
    if credential is not None:
        key, value = credential
        env[key] = value
        secrets_to_redact.append(value)
    projection: dict[str, Any] = {
        "allowlisted_keys": sorted(env),
        "state_mode": "host" if use_host_state else "isolated",
        "home": None if use_host_state else str(home_dir),
        "codebuddy_config_dir": None if use_host_state else str(config_dir),
        "network_environment": network_environment,
        "proxy_configured": {key: bool(env.get(key)) for key in PROXY_ENV_KEYS},
    }
    if credential is not None:
        projection["credential"] = {"name": credential[0], "present": True, "sha256": sha256_bytes(credential[1].encode("utf-8"))}
    return env, projection, secrets_to_redact


@dataclass(frozen=True)
class ProbeContext:
    root: Path
    cli: str
    timeout_sec: int
    allow_agent_cases: bool
    allow_host_login: bool
    use_host_state: bool
    network_environment: str | None
    auth_token: str | None
    api_key: str | None
    api_key_helper: Path | None
    helper_secret: str | None
    sdk_timeout_sec: int
    allow_interactive_login: bool
    update_investigation: bool

    @property
    def config_dir(self) -> Path:
        return self.root / "codebuddy-config"

    @property
    def home_dir(self) -> Path:
        return self.root / "home"


async def pump_stream(stream: asyncio.StreamReader | None, sink: bytearray) -> None:
    if stream is None:
        return
    while chunk := await stream.read(4_096):
        sink.extend(chunk)


async def run_command(
    context: ProbeContext,
    *,
    case: str,
    label: str,
    args: list[str],
    run_dir: Path,
    credential: tuple[str, str] | None = None,
    settings: dict[str, Any] | None = None,
    cancel_after_sec: int | None = None,
    executable: str | None = None,
    additional_redactions: Iterable[str] = (),
    use_host_state: bool | None = None,
    home_dir: Path | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    evidence_dir = context.root / "cases" / case / label
    evidence_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    settings_path: Path | None = None
    command = [executable or context.cli, *args]
    if settings is not None:
        settings_path = run_dir / "probe-settings.json"
        write_json(settings_path, settings)
        command[1:1] = ["--settings", str(settings_path), "--setting-sources", "project"]

    effective_host_state = context.use_host_state if use_host_state is None else use_host_state
    effective_home_dir = home_dir or context.home_dir
    effective_config_dir = config_dir or context.config_dir
    env, environment_projection, secrets_to_redact = sanitize_environment(
        home_dir=effective_home_dir,
        config_dir=effective_config_dir,
        network_environment=context.network_environment,
        use_host_state=effective_host_state,
        credential=credential,
    )
    secrets_to_redact.extend(value for value in additional_redactions if value)
    started_at = utc_iso_now()
    stdout = bytearray()
    stderr = bytearray()
    timed_out = False
    canceled = False
    launch_error: str | None = None
    return_code: int | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(run_dir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=os.name != "nt",
        )
        stdout_task = asyncio.create_task(pump_stream(proc.stdout, stdout))
        stderr_task = asyncio.create_task(pump_stream(proc.stderr, stderr))
        try:
            if cancel_after_sec is None:
                await asyncio.wait_for(proc.wait(), timeout=context.timeout_sec)
            else:
                await asyncio.wait_for(proc.wait(), timeout=cancel_after_sec)
        except asyncio.TimeoutError:
            timed_out = cancel_after_sec is None
            canceled = cancel_after_sec is not None
            if os.name != "nt":
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                if os.name != "nt":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                await proc.wait()
        await asyncio.gather(stdout_task, stderr_task)
        return_code = proc.returncode
    except OSError as exc:
        launch_error = f"{type(exc).__name__}: {exc}"

    stdout_sanitized = redact_bytes(bytes(stdout), secrets_to_redact)
    stderr_sanitized = redact_bytes(bytes(stderr), secrets_to_redact)
    write_bytes(evidence_dir / "stdout.raw", stdout_sanitized)
    write_bytes(evidence_dir / "stderr.raw", stderr_sanitized)
    (evidence_dir / "stdout.txt").write_text(stdout_sanitized.decode("utf-8", errors="replace"), encoding="utf-8")
    (evidence_dir / "stderr.txt").write_text(stderr_sanitized.decode("utf-8", errors="replace"), encoding="utf-8")
    meta = {
        "case": case,
        "label": label,
        "started_at": started_at,
        "finished_at": utc_iso_now(),
        "command": command,
        "cwd": str(run_dir),
        "settings_path": str(settings_path) if settings_path else None,
        "environment": environment_projection,
        "return_code": return_code,
        "timed_out": timed_out,
        "canceled": canceled,
        "launch_error": launch_error,
        "stdout_sha256": sha256_bytes(stdout_sanitized),
        "stderr_sha256": sha256_bytes(stderr_sanitized),
        "stdout_protocol_summary": protocol_summary(stdout_sanitized),
        "config_tree": {"state_mode": "host", "not_snapshotted": True} if effective_host_state else safe_tree(effective_config_dir),
        "run_tree": safe_tree(run_dir),
    }
    write_json(evidence_dir / "meta.json", meta)
    return meta


def require_agent_case(context: ProbeContext, case: str) -> dict[str, Any] | None:
    if context.allow_agent_cases:
        return None
    meta = {
        "case": case,
        "status": "skipped_requires_allow_agent_cases",
        "reason": "Agent cases may perform network requests or access credential providers. Re-run with --allow-agent-cases after supplying dedicated test credentials.",
    }
    write_json(context.root / "cases" / case / "meta.json", meta)
    return meta


def explicit_credential(context: ProbeContext) -> tuple[str, str] | None:
    if context.auth_token:
        return ("CODEBUDDY_AUTH_TOKEN", context.auth_token)
    if context.api_key:
        return ("CODEBUDDY_API_KEY", context.api_key)
    return None


def credential_mode(context: ProbeContext, credential: tuple[str, str] | None) -> str | None:
    if credential is not None:
        return "explicit_env"
    if context.allow_host_login:
        return "host_credential_manager"
    return None


def materialize_workspace(run_dir: Path) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    codebuddy_sentinel = f"CODEBUDDY_SENTINEL_{secrets.token_hex(8)}"
    skill_sentinel = f"SKILL_SENTINEL_{secrets.token_hex(8)}"
    (run_dir / "CODEBUDDY.md").write_text(
        f"When asked to report probe context, include exactly {codebuddy_sentinel}.\n",
        encoding="utf-8",
    )
    skill_path = run_dir / ".codebuddy" / "skills" / "sr-probe" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        "---\nname: sr-probe\ndescription: Emit the CodeBuddy probe sentinel when explicitly invoked.\n---\n\n"
        f"When invoked, include exactly {skill_sentinel} in the response.\n",
        encoding="utf-8",
    )
    return {"codebuddy": codebuddy_sentinel, "skill": skill_sentinel}


async def run_metadata(context: ProbeContext) -> list[dict[str, Any]]:
    run_dir = context.root / "runs" / "metadata"
    node = shutil.which("node")
    return [
        await run_command(context, case="metadata", label="version", args=["--version"], run_dir=run_dir),
        await run_command(context, case="metadata", label="help", args=["--help"], run_dir=run_dir),
        await run_command(context, case="metadata", label="node-version", args=["--version"], run_dir=run_dir, executable=node or "node"),
    ]


async def run_offline_replay(context: ProbeContext) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for sample in sorted(ROOT.glob("artifacts/codebuddy_stdout_sample*.jsonl")):
        raw = sample.read_bytes()
        summary = {"sample": str(sample.relative_to(ROOT)), "protocol_summary": protocol_summary(raw), "sha256": sha256_bytes(raw)}
        summaries.append(summary)
    write_json(context.root / "cases" / "offline-replay" / "meta.json", {"case": "offline-replay", "samples": summaries})
    return summaries


@contextlib.contextmanager
def temporary_environment(env: dict[str, str]) -> Iterable[None]:
    """Run SDK code with a precise inherited environment, then restore it."""

    original = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def sdk_auth_environment(context: ProbeContext) -> tuple[dict[str, str], dict[str, Any]]:
    """Allow intentional host login while excluding inherited explicit credentials."""

    env, projection, _ = sanitize_environment(
        home_dir=context.home_dir,
        config_dir=context.config_dir,
        network_environment=context.network_environment,
        use_host_state=True,
    )
    for key in tuple(env):
        if key.startswith("CODEBUDDY_") and key not in {"CODEBUDDY_CONFIG_DIR", "CODEBUDDY_INTERNET_ENVIRONMENT"}:
            env.pop(key, None)
    projection["explicit_codebuddy_credential_variables_removed"] = True
    return env, projection


def sdk_isolated_environment(
    context: ProbeContext,
    *,
    home_dir: Path,
    config_dir: Path,
) -> tuple[dict[str, str], dict[str, Any]]:
    env, projection, _ = sanitize_environment(
        home_dir=home_dir,
        config_dir=config_dir,
        network_environment=context.network_environment,
        use_host_state=False,
    )
    projection["state_lifetime"] = "temporary_process_scope"
    return env, projection


def sdk_version() -> str | None:
    try:
        return importlib.metadata.version("codebuddy-agent-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None


def secret_occurrence_paths(root: Path, secret: str, *, limit: int = 20) -> dict[str, Any]:
    """Verify that an in-memory credential was not persisted as probe evidence."""

    matched_paths: list[str] = []
    skipped_files = 0
    needle = secret.encode("utf-8")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if needle in path.read_bytes():
                matched_paths.append(str(path.relative_to(root)))
                if len(matched_paths) >= limit:
                    break
        except OSError:
            skipped_files += 1
    return {"matched_paths": matched_paths, "truncated": len(matched_paths) >= limit, "skipped_files": skipped_files}


def jwt_temporal_metadata(token: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "length": len(token),
        "sha256": sha256_bytes(token.encode("utf-8")),
    }
    parts = token.split(".")
    if len(parts) != 3:
        metadata["format"] = "opaque"
        return metadata
    metadata["format"] = "jwt"
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        )
    except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
        metadata["payload_parse_error"] = type(exc).__name__
        return metadata
    temporal = {
        key: payload[key]
        for key in ("iat", "nbf", "exp")
        if isinstance(payload.get(key), (int, float))
    }
    metadata["temporal"] = temporal
    if isinstance(temporal.get("iat"), (int, float)) and isinstance(temporal.get("exp"), (int, float)):
        metadata["ttl_seconds"] = int(temporal["exp"] - temporal["iat"])
    return metadata


class AuthResultRecordingReader:
    """Capture the SDK auth callback shape without retaining user or token data."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.summary: dict[str, Any] | None = None

    def __aiter__(self) -> AuthResultRecordingReader:
        return self

    async def __anext__(self) -> dict[str, Any]:
        message = await self._inner.__anext__()
        request = message.get("request") if isinstance(message, dict) else None
        if (
            message.get("type") == "control_request"
            and isinstance(request, dict)
            and request.get("subtype") == "auth_result_callback"
        ):
            error = request.get("error")
            userinfo = request.get("userinfo")
            self.summary = {
                "received": True,
                "success": bool(request.get("success")),
                "error_type": error.get("type") if isinstance(error, dict) else None,
                "error_message_present": bool(error.get("message")) if isinstance(error, dict) else False,
                "userinfo_token_present": bool(userinfo.get("token")) if isinstance(userinfo, dict) else False,
            }
        return message


async def run_sdk_auth_token(context: ProbeContext) -> list[dict[str, Any]]:
    skipped = require_agent_case(context, "sdk-auth-token")
    if skipped is not None:
        return [skipped]
    if not context.allow_host_login:
        meta = {
            "case": "sdk-auth-token",
            "status": "skipped_requires_allow_host_login",
            "reason": "The SDK acquisition probe deliberately reads the host CodeBuddy login state.",
        }
        write_json(context.root / "cases" / "sdk-auth-token" / "meta.json", meta)
        return [meta]
    installed_sdk_version = sdk_version()
    if installed_sdk_version is None:
        meta = {
            "case": "sdk-auth-token",
            "status": "skipped_sdk_not_installed",
            "package": "codebuddy-agent-sdk",
        }
        write_json(context.root / "cases" / "sdk-auth-token" / "meta.json", meta)
        return [meta]

    sdk_env, sdk_environment_projection = sdk_auth_environment(context)
    auth_meta: dict[str, Any] = {
        "case": "sdk-auth-token",
        "label": "sdk-acquisition",
        "sdk_version": installed_sdk_version,
        "cli": context.cli,
        "python_version": sys.version,
        "environment": sdk_environment_projection,
        "started_at": utc_iso_now(),
    }
    token: str | None = None
    try:
        from codebuddy_agent_sdk import authenticate

        with temporary_environment(sdk_env):
            flow = await authenticate(
                codebuddy_code_path=context.cli,
                environment=context.network_environment,
                timeout=context.sdk_timeout_sec,
            )
            auth_meta["auth_url_present"] = bool(flow.auth_url)
            auth_meta["auth_url_host"] = urlsplit(flow.auth_url).hostname if flow.auth_url else None
            auth_meta["method_id"] = flow.method_id
            result = await flow.wait(timeout=context.sdk_timeout_sec)
        token = result.userinfo.token or None
        auth_meta["status"] = "completed"
        auth_meta["token_present"] = bool(token)
        if token:
            auth_meta["token"] = {
                "length": len(token),
                "sha256": sha256_bytes(token.encode("utf-8")),
            }
    except Exception as exc:  # The SDK has several public and transport-specific error types.
        auth_meta.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": redact_bytes(str(exc).encode("utf-8"), [token or ""]).decode("utf-8", errors="replace"),
                "token_present": False,
            }
        )
    auth_meta["finished_at"] = utc_iso_now()
    write_json(context.root / "cases" / "sdk-auth-token" / "sdk-acquisition" / "meta.json", auth_meta)

    base = ["-p", "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]
    run_dir = context.root / "runs" / "sdk-auth-token"
    host_control = await run_command(
        context,
        case="sdk-auth-token",
        label="host-state-control",
        args=[*base, "Reply exactly with PROBE_SDK_HOST_CONTROL."],
        run_dir=run_dir / "host-state-control",
        use_host_state=True,
    )
    invalid_auth_token = await run_command(
        context,
        case="sdk-auth-token",
        label="invalid-auth-token-host-state",
        args=[*base, "Reply exactly with PROBE_SDK_INVALID_AUTH_TOKEN."],
        run_dir=run_dir / "invalid-auth-token-host-state",
        credential=("CODEBUDDY_AUTH_TOKEN", "skill-runner-probe-invalid-auth-token"),
        use_host_state=True,
    )
    isolated_without_token = await run_command(
        context,
        case="sdk-auth-token",
        label="isolated-without-token",
        args=[*base, "Reply exactly with PROBE_SDK_ISOLATED_WITHOUT_TOKEN."],
        run_dir=run_dir / "isolated-without-token",
        use_host_state=False,
    )
    records = [auth_meta, host_control, invalid_auth_token, isolated_without_token]
    if token is None:
        records.append(
            {
                "case": "sdk-auth-token",
                "label": "isolated-with-sdk-token",
                "status": "skipped_sdk_returned_no_token",
            }
        )
        return records
    try:
        records.append(
            await run_command(
                context,
                case="sdk-auth-token",
                label="isolated-with-sdk-token",
                args=[*base, "Reply exactly with PROBE_SDK_ISOLATED_WITH_TOKEN."],
                run_dir=run_dir / "isolated-with-sdk-token",
                credential=("CODEBUDDY_AUTH_TOKEN", token),
                use_host_state=False,
            )
        )
    finally:
        auth_meta["evidence_token_occurrences"] = secret_occurrence_paths(context.root, token)
        write_json(context.root / "cases" / "sdk-auth-token" / "sdk-acquisition" / "meta.json", auth_meta)
        token = None
    return records


async def run_sdk_interactive_auth(context: ProbeContext) -> list[dict[str, Any]]:
    skipped = require_agent_case(context, "sdk-interactive-auth")
    if skipped is not None:
        return [skipped]
    if not context.allow_interactive_login:
        meta = {
            "case": "sdk-interactive-auth",
            "status": "skipped_requires_allow_interactive_login",
            "reason": "This case prints a one-time authentication URL and waits for operator completion.",
        }
        write_json(context.root / "cases" / "sdk-interactive-auth" / "meta.json", meta)
        return [meta]
    installed_sdk_version = sdk_version()
    if installed_sdk_version is None:
        meta = {
            "case": "sdk-interactive-auth",
            "status": "skipped_sdk_not_installed",
            "package": "codebuddy-agent-sdk",
        }
        write_json(context.root / "cases" / "sdk-interactive-auth" / "meta.json", meta)
        return [meta]

    auth_meta: dict[str, Any] = {
        "case": "sdk-interactive-auth",
        "label": "sdk-isolated-interactive-acquisition",
        "sdk_version": installed_sdk_version,
        "cli": context.cli,
        "python_version": sys.version,
        "sdk_environment": context.network_environment,
        "started_at": utc_iso_now(),
    }
    token: str | None = None
    try:
        from codebuddy_agent_sdk import authenticate

        with tempfile.TemporaryDirectory(prefix="skill-runner-codebuddy-sdk-auth-") as sdk_state_root_raw:
            sdk_state_root = Path(sdk_state_root_raw)
            sdk_home = sdk_state_root / "home"
            sdk_config = sdk_state_root / "config"
            sdk_env, sdk_environment_projection = sdk_isolated_environment(
                context,
                home_dir=sdk_home,
                config_dir=sdk_config,
            )
            auth_meta["environment"] = sdk_environment_projection
            with temporary_environment(sdk_env):
                flow = await authenticate(
                    codebuddy_code_path=context.cli,
                    environment=context.network_environment,
                    timeout=context.sdk_timeout_sec,
                )
                auth_meta["auth_url_present"] = bool(flow.auth_url)
                auth_meta["auth_url_host"] = urlsplit(flow.auth_url).hostname if flow.auth_url else None
                auth_meta["method_id"] = flow.method_id
                if not flow.auth_url:
                    auth_meta["status"] = "unexpected_already_authenticated"
                    await flow.cancel()
                else:
                    auth_meta["auth_url_disclosed_to_operator"] = True
                    print(f"CODEBUDDY_AUTH_URL={flow.auth_url}", flush=True)
                    recording_reader = AuthResultRecordingReader(flow._reader)
                    flow._reader = recording_reader
                    result = await flow.wait(timeout=context.sdk_timeout_sec)
                    auth_meta["auth_result_callback"] = recording_reader.summary
                    token = result.userinfo.token or None
                    auth_meta["token_present"] = bool(token)
                    if token:
                        auth_meta["token"] = {
                            "length": len(token),
                            "sha256": sha256_bytes(token.encode("utf-8")),
                        }
                        auth_meta["sdk_state_token_occurrence_count"] = len(
                            secret_occurrence_paths(sdk_state_root, token)["matched_paths"]
                        )
    except Exception as exc:  # The SDK reports user cancellation, timeout, and transport failures through public error types.
        if "recording_reader" in locals():
            auth_meta["auth_result_callback"] = recording_reader.summary
        auth_meta.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": redact_bytes(str(exc).encode("utf-8"), [token or ""]).decode("utf-8", errors="replace"),
                "token_present": False,
            }
        )

    if token is None:
        auth_meta.setdefault("status", "completed_without_token")
        auth_meta["finished_at"] = utc_iso_now()
        write_json(context.root / "cases" / "sdk-interactive-auth" / "sdk-acquisition" / "meta.json", auth_meta)
        return [auth_meta]

    records: list[dict[str, Any]] = [auth_meta]
    try:
        with tempfile.TemporaryDirectory(prefix="skill-runner-codebuddy-sdk-cli-") as cli_state_root_raw:
            cli_state_root = Path(cli_state_root_raw)
            cli_home = cli_state_root / "home"
            cli_config = cli_state_root / "config"
            base = ["-p", "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]
            run_dir = context.root / "runs" / "sdk-interactive-auth"
            records.append(
                await run_command(
                    context,
                    case="sdk-interactive-auth",
                    label="fresh-cli-without-token",
                    args=[*base, "Reply exactly with PROBE_SDK_INTERACTIVE_WITHOUT_TOKEN."],
                    run_dir=run_dir / "without-token",
                    use_host_state=False,
                    home_dir=cli_home,
                    config_dir=cli_config,
                )
            )
            records.append(
                await run_command(
                    context,
                    case="sdk-interactive-auth",
                    label="fresh-cli-with-sdk-token",
                    args=[*base, "Reply exactly with PROBE_SDK_INTERACTIVE_WITH_TOKEN."],
                    run_dir=run_dir / "with-token",
                    credential=("CODEBUDDY_AUTH_TOKEN", token),
                    use_host_state=False,
                    home_dir=cli_home,
                    config_dir=cli_config,
                )
            )
            auth_meta["cli_state_token_occurrence_count"] = len(
                secret_occurrence_paths(cli_state_root, token)["matched_paths"]
            )
        auth_meta["status"] = "completed"
    finally:
        auth_meta["evidence_token_occurrences"] = secret_occurrence_paths(context.root, token)
        auth_meta["finished_at"] = utc_iso_now()
        write_json(context.root / "cases" / "sdk-interactive-auth" / "sdk-acquisition" / "meta.json", auth_meta)
        token = None
    return records


async def run_service_config_isolation(context: ProbeContext) -> list[dict[str, Any]]:
    skipped = require_agent_case(context, "service-config-isolation")
    if skipped is not None:
        return [skipped]
    if not context.allow_host_login:
        meta = {
            "case": "service-config-isolation",
            "status": "skipped_requires_allow_host_login",
            "reason": "The service-config probe acquires an in-memory token from the authorized host login, then isolates every CLI turn.",
        }
        write_json(context.root / "cases" / "service-config-isolation" / "meta.json", meta)
        return [meta]
    installed_sdk_version = sdk_version()
    if installed_sdk_version is None:
        meta = {
            "case": "service-config-isolation",
            "status": "skipped_sdk_not_installed",
            "package": "codebuddy-agent-sdk",
        }
        write_json(context.root / "cases" / "service-config-isolation" / "meta.json", meta)
        return [meta]

    acquisition: dict[str, Any] = {
        "case": "service-config-isolation",
        "label": "host-sdk-token-acquisition",
        "sdk_version": installed_sdk_version,
        "started_at": utc_iso_now(),
    }
    token: str | None = None
    try:
        from codebuddy_agent_sdk import authenticate

        sdk_env, sdk_environment_projection = sdk_auth_environment(context)
        acquisition["environment"] = sdk_environment_projection
        with temporary_environment(sdk_env):
            flow = await authenticate(
                codebuddy_code_path=context.cli,
                environment=context.network_environment,
                timeout=context.sdk_timeout_sec,
            )
            acquisition["auth_url_present"] = bool(flow.auth_url)
            if flow.auth_url:
                await flow.cancel()
                acquisition["status"] = "unexpected_login_required"
            else:
                result = await flow.wait(timeout=context.sdk_timeout_sec)
                token = result.userinfo.token or None
                acquisition["status"] = "completed" if token else "completed_without_token"
                acquisition["token_present"] = bool(token)
                if token:
                    acquisition["token"] = {
                        "length": len(token),
                        "sha256": sha256_bytes(token.encode("utf-8")),
                    }
    except Exception as exc:
        acquisition.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": redact_bytes(str(exc).encode("utf-8"), [token or ""]).decode("utf-8", errors="replace"),
                "token_present": False,
            }
        )
    acquisition["finished_at"] = utc_iso_now()
    write_json(context.root / "cases" / "service-config-isolation" / "host-sdk-token-acquisition.json", acquisition)
    if token is None:
        return [acquisition]

    service_home = context.home_dir
    service_config = context.config_dir
    run_dir = context.root / "runs" / "service-config-isolation"
    run_dir.mkdir(parents=True, exist_ok=True)
    project_sentinel = f"SR_PROJECT_SETTINGS_{secrets.token_hex(8)}"
    user_sentinel = f"SR_USER_SETTINGS_{secrets.token_hex(8)}"
    write_json(run_dir / ".codebuddy" / "settings.json", {"env": {"SR_PROJECT_SETTINGS_SENTINEL": project_sentinel}})
    write_json(service_home / ".codebuddy" / "settings.json", {"env": {"SR_USER_SETTINGS_SENTINEL": user_sentinel}})
    write_json(service_config / "settings.json", {"env": {"SR_USER_SETTINGS_SENTINEL": user_sentinel}})
    materialize_workspace(run_dir)
    base = ["-p", "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]
    controlled_settings = {"disableAllHooks": True}
    records: list[dict[str, Any]] = [acquisition]
    settings_check = await run_command(
        context,
        case="service-config-isolation",
        label="settings-source-check",
        args=[
            *base,
            "Use Bash exactly once to run: printf 'project=%s user=%s\\n' \"${SR_PROJECT_SETTINGS_SENTINEL:-absent}\" \"${SR_USER_SETTINGS_SENTINEL:-absent}\". Then reply exactly with that printed line.",
        ],
        run_dir=run_dir,
        credential=("CODEBUDDY_AUTH_TOKEN", token),
        settings=controlled_settings,
        use_host_state=False,
        home_dir=service_home,
        config_dir=service_config,
    )
    records.append(settings_check)
    settings_stdout = (context.root / "cases" / "service-config-isolation" / "settings-source-check" / "stdout.raw").read_bytes()
    settings_observation = {
        "project_sentinel_observed": project_sentinel.encode("utf-8") in settings_stdout,
        "user_sentinel_observed": user_sentinel.encode("utf-8") in settings_stdout,
    }

    session_id = f"probe-service-config-{secrets.token_hex(12)}"
    started = await run_command(
        context,
        case="service-config-isolation",
        label="start",
        args=[*base, "--session-id", session_id, "Reply exactly with PROBE_SERVICE_CONFIG_START."],
        run_dir=run_dir,
        credential=("CODEBUDDY_AUTH_TOKEN", token),
        settings=controlled_settings,
        use_host_state=False,
        home_dir=service_home,
        config_dir=service_config,
    )
    resumed = await run_command(
        context,
        case="service-config-isolation",
        label="resume-after-new-process",
        args=[*base, "-r", session_id, "Reply exactly with PROBE_SERVICE_CONFIG_RESUMED."],
        run_dir=run_dir,
        credential=("CODEBUDDY_AUTH_TOKEN", token),
        settings=controlled_settings,
        use_host_state=False,
        home_dir=service_home,
        config_dir=service_config,
    )
    records.extend([started, resumed])

    async def concurrent_turn(label: str) -> dict[str, Any]:
        return await run_command(
            context,
            case="service-config-isolation",
            label=f"concurrent-{label}",
            args=[*base, "--session-id", f"probe-service-config-{label}-{secrets.token_hex(12)}", f"Reply exactly with PROBE_SERVICE_CONFIG_CONCURRENT_{label.upper()}."],
            run_dir=run_dir / label,
            credential=("CODEBUDDY_AUTH_TOKEN", token),
            settings=controlled_settings,
            use_host_state=False,
            home_dir=service_home,
            config_dir=service_config,
        )

    concurrent = list(await asyncio.gather(concurrent_turn("left"), concurrent_turn("right")))
    records.extend(concurrent)
    summary = {
        "case": "service-config-isolation",
        "service_home": str(service_home),
        "service_config": str(service_config),
        "settings_source": "project",
        "settings_observation": settings_observation,
        "expected_resume_session_id": session_id,
        "start_session_ids": started["stdout_protocol_summary"]["session_ids"],
        "resume_session_ids": resumed["stdout_protocol_summary"]["session_ids"],
        "concurrent_session_ids": {
            item["label"]: item["stdout_protocol_summary"]["session_ids"] for item in concurrent
        },
        "service_config_token_occurrences": len(secret_occurrence_paths(service_config, token)["matched_paths"]),
        "evidence_token_occurrences": secret_occurrence_paths(context.root, token),
        "service_home_tree": safe_tree(service_home),
        "service_config_tree": safe_tree(service_config),
    }
    write_json(context.root / "cases" / "service-config-isolation" / "summary.json", summary)
    token = None
    return records


async def run_sdk_token_lifecycle(context: ProbeContext) -> list[dict[str, Any]]:
    skipped = require_agent_case(context, "sdk-token-lifecycle")
    if skipped is not None:
        return [skipped]
    if not context.allow_host_login:
        meta = {
            "case": "sdk-token-lifecycle",
            "status": "skipped_requires_allow_host_login",
            "reason": "This probe compares two in-memory SDK acquisitions from the authorized host login.",
        }
        write_json(context.root / "cases" / "sdk-token-lifecycle" / "meta.json", meta)
        return [meta]
    if sdk_version() is None:
        meta = {"case": "sdk-token-lifecycle", "status": "skipped_sdk_not_installed"}
        write_json(context.root / "cases" / "sdk-token-lifecycle" / "meta.json", meta)
        return [meta]

    async def acquire() -> tuple[str | None, dict[str, Any]]:
        sdk_env, projection = sdk_auth_environment(context)
        meta: dict[str, Any] = {"environment": projection}
        try:
            from codebuddy_agent_sdk import authenticate

            with temporary_environment(sdk_env):
                flow = await authenticate(
                    codebuddy_code_path=context.cli,
                    environment=context.network_environment,
                    timeout=context.sdk_timeout_sec,
                )
                meta["auth_url_present"] = bool(flow.auth_url)
                if flow.auth_url:
                    await flow.cancel()
                    meta["status"] = "unexpected_login_required"
                    return None, meta
                result = await flow.wait(timeout=context.sdk_timeout_sec)
            token = result.userinfo.token or None
            meta["status"] = "completed" if token else "completed_without_token"
            if token:
                meta.update(jwt_temporal_metadata(token))
            return token, meta
        except Exception as exc:
            meta.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": redact_bytes(str(exc).encode("utf-8"), []).decode("utf-8", errors="replace"),
                }
            )
            return None, meta

    first_token, first = await acquire()
    second_token, second = await acquire()
    meta = {
        "case": "sdk-token-lifecycle",
        "sdk_version": sdk_version(),
        "first": first,
        "second": second,
        "same_token_sha256": bool(first_token and second_token and first_token == second_token),
        "same_expiry": first.get("temporal", {}).get("exp") == second.get("temporal", {}).get("exp"),
    }
    if first_token:
        meta["evidence_token_occurrences"] = secret_occurrence_paths(context.root, first_token)
    if second_token and second_token != first_token:
        meta["second_token_evidence_occurrences"] = secret_occurrence_paths(context.root, second_token)
    write_json(context.root / "cases" / "sdk-token-lifecycle" / "meta.json", meta)
    first_token = None
    second_token = None
    return [meta]


async def run_agent_case(context: ProbeContext, case: str) -> list[dict[str, Any]]:
    skipped = require_agent_case(context, case)
    if skipped is not None:
        return [skipped]
    if case == "sdk-auth-token":
        return await run_sdk_auth_token(context)
    if case == "sdk-interactive-auth":
        return await run_sdk_interactive_auth(context)
    if case == "service-config-isolation":
        return await run_service_config_isolation(context)
    if case == "sdk-token-lifecycle":
        return await run_sdk_token_lifecycle(context)
    run_dir = context.root / "runs" / case
    base = ["-p", "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]
    credential = explicit_credential(context)
    mode = credential_mode(context, credential)
    if case == "unauthenticated":
        return [await run_command(context, case=case, label="empty", args=[*base, "Reply with PROBE_UNAUTHENTICATED."], run_dir=run_dir)]
    if case == "document-sample-1":
        if mode is None:
            meta = {
                "case": case,
                "status": "skipped_missing_credential",
                "reason": "The documented command is a real agent turn and requires an explicit credential or authorized host login.",
            }
            write_json(context.root / "cases" / case / "meta.json", meta)
            return [meta]
        return [
            await run_command(
                context,
                case=case,
                label=mode,
                args=[*base, DOCUMENT_SAMPLE_1_PROMPT],
                run_dir=run_dir,
                credential=credential,
            )
        ]
    if case == "document-sample-2":
        if mode is None:
            meta = {
                "case": case,
                "status": "skipped_missing_credential",
                "reason": "The documented multi-turn command sequence requires an explicit credential or authorized host login.",
            }
            write_json(context.root / "cases" / case / "meta.json", meta)
            return [meta]
        session_id = f"probe-doc-sample-2-{secrets.token_hex(12)}"
        first = await run_command(
            context,
            case=case,
            label="attempt-1",
            args=[*base, "--session-id", session_id, DOCUMENT_SAMPLE_2_PROMPTS[0]],
            run_dir=run_dir,
            credential=credential,
        )
        resumed: list[dict[str, Any]] = [first]
        for index, prompt in enumerate(DOCUMENT_SAMPLE_2_PROMPTS[1:], start=2):
            resumed.append(
                await run_command(
                    context,
                    case=case,
                    label=f"attempt-{index}",
                    args=[*base, "-r", session_id, prompt],
                    run_dir=run_dir,
                    credential=credential,
                )
            )
        return resumed
    if case == "invalid-api-key":
        return [await run_command(context, case=case, label="invalid", args=[*base, "Reply with PROBE_INVALID_KEY."], run_dir=run_dir, credential=("CODEBUDDY_API_KEY", "skill-runner-probe-invalid-key"))]
    if case == "helper-credential":
        if context.api_key_helper is None:
            meta = {"case": case, "status": "skipped_missing_api_key_helper"}
            write_json(context.root / "cases" / case / "meta.json", meta)
            return [meta]
        if not context.helper_secret:
            meta = {"case": case, "status": "skipped_missing_helper_redaction_secret"}
            write_json(context.root / "cases" / case / "meta.json", meta)
            return [meta]
        return [await run_command(context, case=case, label="helper", args=[*base, "Reply with PROBE_HELPER_CREDENTIAL."], run_dir=run_dir, settings={"apiKeyHelper": str(context.api_key_helper)}, additional_redactions=[context.helper_secret])]
    if mode is None:
        meta = {"case": case, "status": "skipped_missing_credential", "accepted_environment_variables": ["SKILL_RUNNER_CODEBUDDY_PROBE_AUTH_TOKEN", "SKILL_RUNNER_CODEBUDDY_PROBE_API_KEY"], "host_login_requires": "--allow-host-login"}
        write_json(context.root / "cases" / case / "meta.json", meta)
        return [meta]
    if case == "explicit-credential":
        return [await run_command(context, case=case, label=mode, args=[*base, "Reply exactly with PROBE_EXPLICIT_CREDENTIAL."], run_dir=run_dir, credential=credential)]
    if case == "materialization":
        sentinels = materialize_workspace(run_dir)
        meta = await run_command(context, case=case, label="skill-and-instructions", args=[*base, "/sr-probe\nReport both configured probe sentinels."], run_dir=run_dir, credential=credential, settings={"disableAllHooks": True})
        meta["expected_sentinels"] = sentinels
        write_json(context.root / "cases" / case / "skill-and-instructions" / "meta.json", meta)
        return [meta]
    if case in {"structured-json", "structured-stream"}:
        output_format = "json" if case == "structured-json" else "stream-json"
        schema = {"type": "object", "properties": {"probe": {"type": "string"}}, "required": ["probe"], "additionalProperties": False}
        return [await run_command(context, case=case, label=output_format, args=["-p", "--output-format", output_format, "--permission-mode", "bypassPermissions", "--json-schema", json.dumps(schema), "Return a JSON object whose probe value is schema-ok."], run_dir=run_dir, credential=credential)]
    if case == "tool-event":
        prompt = "Use Bash to write exactly tool-event to .probe-tool-output.txt, read it back, then report completion."
        return [await run_command(context, case=case, label="write-read", args=[*base, prompt], run_dir=run_dir, credential=credential)]
    if case == "resume":
        session_id = f"probe-{secrets.token_hex(12)}"
        first = await run_command(context, case=case, label="start", args=[*base, "--session-id", session_id, "Reply exactly with PROBE_RESUME_START."], run_dir=run_dir, credential=credential)
        resumed = await run_command(context, case=case, label="resume", args=[*base, "-r", session_id, "Reply exactly with PROBE_RESUME_CONTINUED."], run_dir=run_dir, credential=credential)
        return [first, resumed]
    if case == "cancel":
        prompt = "Use Bash to run sleep 120 before responding. Do not provide a final response before the command completes."
        return [await run_command(context, case=case, label="terminate", args=[*base, prompt], run_dir=run_dir, credential=credential, cancel_after_sec=10)]
    if case == "concurrency":
        async def one(label: str) -> dict[str, Any]:
            return await run_command(context, case=case, label=label, args=[*base, "--session-id", f"probe-{secrets.token_hex(12)}", f"Reply exactly with PROBE_CONCURRENCY_{label.upper()}."], run_dir=run_dir / label, credential=credential)

        return list(await asyncio.gather(one("left"), one("right")))
    raise ValueError(f"Unsupported agent case: {case}")


def case_conclusion(case: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(item.get("status") or "completed") for item in results]
    return {
        "case": case,
        "status": "skipped" if all(status.startswith("skipped_") for status in statuses) else "captured",
        "records": len(results),
        "return_codes": [item.get("return_code") for item in results if "return_code" in item],
        "timed_out": any(bool(item.get("timed_out")) for item in results),
        "canceled": any(bool(item.get("canceled")) for item in results),
    }


def append_investigation_summary(context: ProbeContext, summary: dict[str, Any]) -> None:
    path = ROOT / "artifacts" / "codebuddy_engine_investigation_2026-07-10.md"
    lines = ["", "## Probe Run Summary", "", f"Probe root: `{summary['probe_root']}`", "", "| Case | Status | Records | Return codes |", "| --- | --- | ---: | --- |"]
    for item in summary["cases"]:
        lines.append(f"| {item['case']} | {item['status']} | {item['records']} | {item['return_codes']} |")
    lines.extend(["", "The raw evidence is ignored local data. It contains sanitized stdout/stderr only; credentials and full environment values are not recorded.", ""])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Capture secret-safe CodeBuddy CLI probe evidence")
    parser.add_argument("--cli", default=shutil.which("codebuddy") or "codebuddy", help="CodeBuddy executable")
    parser.add_argument("--output-root", type=Path, help="Ignored data directory for this probe run")
    parser.add_argument("--cases", nargs="+", choices=CASE_CHOICES, default=list(DEFAULT_CASES))
    parser.add_argument("--timeout", type=int, default=180, help="Per agent process timeout in seconds")
    parser.add_argument("--allow-agent-cases", action="store_true", help="Allow cases that start CodeBuddy agent turns")
    parser.add_argument("--allow-host-login", action="store_true", help="Permit agent cases without explicit credentials to use the operating-system credential manager")
    parser.add_argument("--use-host-state", action="store_true", help="Use the host HOME and CodeBuddy configuration state; requires --allow-host-login")
    parser.add_argument("--network-environment", choices=("public", "internal", "ioa"), help="Value for CODEBUDDY_INTERNET_ENVIRONMENT")
    parser.add_argument("--auth-token-env", default="SKILL_RUNNER_CODEBUDDY_PROBE_AUTH_TOKEN", help="Environment variable that holds a dedicated probe auth token")
    parser.add_argument("--api-key-env", default="SKILL_RUNNER_CODEBUDDY_PROBE_API_KEY", help="Environment variable that holds a dedicated probe API key")
    parser.add_argument("--api-key-helper", type=Path, help="Dedicated helper executable for helper-credential case")
    parser.add_argument("--api-key-helper-secret-env", default="SKILL_RUNNER_CODEBUDDY_PROBE_HELPER_SECRET", help="Environment variable used only to redact the helper's emitted credential")
    parser.add_argument("--sdk-timeout", type=int, default=300, help="Maximum seconds to wait for SDK authentication completion")
    parser.add_argument("--allow-interactive-login", action="store_true", help="Allow SDK cases to print a one-time login URL and wait for operator completion")
    parser.add_argument("--update-investigation", action="store_true", help="Append the sanitized run summary to the investigation artifact")
    args = parser.parse_args()

    if args.timeout < 1 or args.timeout > 300:
        parser.error("--timeout must be between 1 and 300 seconds")
    if args.sdk_timeout < 1 or args.sdk_timeout > 300:
        parser.error("--sdk-timeout must be between 1 and 300 seconds")
    if args.use_host_state and not args.allow_host_login:
        parser.error("--use-host-state requires --allow-host-login")
    cli = str(Path(args.cli).expanduser()) if Path(args.cli).exists() else args.cli
    output_root = (args.output_root or ROOT / "data" / "codebuddy_probes" / utc_now()).resolve()
    context = ProbeContext(
        root=output_root,
        cli=cli,
        timeout_sec=args.timeout,
        allow_agent_cases=bool(args.allow_agent_cases),
        allow_host_login=bool(args.allow_host_login),
        use_host_state=bool(args.use_host_state),
        network_environment=args.network_environment,
        auth_token=os.environ.get(args.auth_token_env),
        api_key=os.environ.get(args.api_key_env),
        api_key_helper=args.api_key_helper.resolve() if args.api_key_helper else None,
        helper_secret=os.environ.get(args.api_key_helper_secret_env),
        sdk_timeout_sec=args.sdk_timeout,
        allow_interactive_login=bool(args.allow_interactive_login),
        update_investigation=bool(args.update_investigation),
    )
    if context.api_key_helper is not None and not context.api_key_helper.is_file():
        parser.error("--api-key-helper must name an existing file")
    context.root.mkdir(parents=True, exist_ok=False)
    write_json(
        context.root / "run.json",
        {
            "started_at": utc_iso_now(),
            "cli": context.cli,
            "cases": args.cases,
            "allow_agent_cases": context.allow_agent_cases,
            "allow_host_login": context.allow_host_login,
            "use_host_state": context.use_host_state,
            "network_environment": context.network_environment,
            "credential_sources_present": {"auth_token": bool(context.auth_token), "api_key": bool(context.api_key), "api_key_helper": bool(context.api_key_helper), "helper_redaction_secret": bool(context.helper_secret)},
        },
    )

    all_results: dict[str, list[dict[str, Any]]] = {}
    for case in args.cases:
        if case == "metadata":
            all_results[case] = await run_metadata(context)
        elif case == "offline-replay":
            all_results[case] = await run_offline_replay(context)
        else:
            all_results[case] = await run_agent_case(context, case)
    summary = {"probe_root": str(context.root.relative_to(ROOT)), "finished_at": utc_iso_now(), "cases": [case_conclusion(case, results) for case, results in all_results.items()]}
    write_json(context.root / "summary.json", summary)
    if context.update_investigation:
        append_investigation_summary(context, summary)
    print(context.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
