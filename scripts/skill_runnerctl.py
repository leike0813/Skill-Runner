#!/usr/bin/env python
"""Control utility for Skill Runner local/docker lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services.engine_management.runtime_profile import get_runtime_profile

WINDOWS_NPM_CANDIDATES = ("npm.cmd", "npm.exe", "npm.bat", "npm")
DEFAULT_SERVICE_PORT = 9813
DEFAULT_PLUGIN_LOCAL_PORT = 29813
INTEGRITY_MANIFEST_NAME = "release_integrity_manifest.json"


def _windows_subprocess_options(*, detached: bool = False) -> dict[str, Any]:
    if not sys.platform.startswith("win"):
        return {}
    options: dict[str, Any] = {}
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if detached:
        creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
        creationflags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    if creationflags:
        options["creationflags"] = creationflags
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    startf_use_showwindow = int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
    if startupinfo_factory is not None and startf_use_showwindow:
        startupinfo = startupinfo_factory()
        startupinfo.dwFlags |= startf_use_showwindow
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
        options["startupinfo"] = startupinfo
    return options


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(payload: dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload.get("message", payload))
    return int(payload.get("exit_code", 0))


def _command_exists(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _default_ctl_port() -> int:
    if "SKILL_RUNNER_LOCAL_PORT" in os.environ:
        return _int_from_env("SKILL_RUNNER_LOCAL_PORT", DEFAULT_PLUGIN_LOCAL_PORT)
    if "PORT" in os.environ:
        return _int_from_env("PORT", DEFAULT_SERVICE_PORT)
    return DEFAULT_SERVICE_PORT


def _default_ctl_fallback_span() -> int:
    span = _int_from_env("SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN", 0)
    return max(0, span)


def _project_root() -> Path:
    return PROJECT_ROOT


def _state_file(profile) -> Path:
    return profile.agent_cache_root / "local_runtime_service.json"


def _local_logs_file(profile) -> Path:
    return profile.data_dir / "logs" / "local_runtime_service.log"


def _build_service_url(host: str, port: int, path: str = "/") -> str:
    safe_path = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{port}{safe_path}"


def _http_json(
    method: str, url: str, *, payload: dict[str, Any] | None = None, timeout: float = 3.0
) -> tuple[int | None, dict[str, Any] | None]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urlrequest.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return int(resp.status), {}
            return int(resp.status), json.loads(raw)
    except urlerror.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            return int(exc.code), json.loads(raw)
        except (json.JSONDecodeError, OSError, ValueError):
            return int(exc.code), {"detail": str(exc)}
    except (urlerror.URLError, TimeoutError, OSError):
        return None, None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        cmd = ["tasklist", "/FI", f"PID eq {pid}"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            **_windows_subprocess_options(),
        )
        return str(pid) in (proc.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_pid(pid: int) -> None:
    if pid <= 0:
        return
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            **_windows_subprocess_options(),
        )
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return


def _load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_state(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def _is_valid_port(port: int) -> bool:
    return 1 <= port <= 65535


def _can_bind_port(host: str, port: int) -> bool:
    if not _is_valid_port(port):
        return False
    bind_host = host.strip()
    if bind_host in {"", "0.0.0.0", "::"}:
        bind_host = ""
    try:
        infos = socket.getaddrinfo(
            bind_host,
            port,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
            0,
            socket.AI_PASSIVE,
        )
    except socket.gaierror:
        return False
    seen: set[tuple[Any, ...]] = set()
    for family, socktype, proto, _, sockaddr in infos:
        if isinstance(sockaddr, tuple):
            sockaddr_id: tuple[Any, ...] = (sockaddr[0], sockaddr[1])
        else:
            sockaddr_id = (sockaddr,)
        key = (family, socktype, proto, sockaddr_id)
        if key in seen:
            continue
        seen.add(key)
        test_socket: socket.socket | None = None
        try:
            test_socket = socket.socket(family, socktype, proto)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind(sockaddr)
            return True
        except OSError:
            continue
        finally:
            if test_socket is not None:
                test_socket.close()
    return False


def _select_port_with_fallback(host: str, requested_port: int, fallback_span: int) -> tuple[int | None, list[int]]:
    max_port = min(65535, requested_port + max(0, fallback_span))
    tried_ports = list(range(requested_port, max_port + 1))
    for candidate in tried_ports:
        if _can_bind_port(host, candidate):
            return candidate, tried_ports
    return None, tried_ports


def _runtime_env() -> tuple[Any, dict[str, str]]:
    profile = get_runtime_profile()
    profile.ensure_directories()
    env = profile.build_subprocess_env()
    if sys.platform.startswith("win"):
        path_env = env.get("PATH", "")
        resolved_npm = ""
        for candidate in WINDOWS_NPM_CANDIDATES:
            found = shutil.which(candidate, path=path_env)
            if found:
                resolved_npm = found
                break
        if resolved_npm:
            npm_path = Path(resolved_npm)
            if npm_path.suffix.lower() == ".ps1":
                cmd_sibling = npm_path.with_suffix(".cmd")
                if cmd_sibling.exists():
                    npm_path = cmd_sibling
            env["SKILL_RUNNER_NPM_COMMAND"] = str(npm_path)
            npm_dir = str(npm_path.parent)
            path_parts = [part for part in path_env.split(os.pathsep) if part]
            if npm_dir and npm_dir not in path_parts:
                env["PATH"] = f"{npm_dir}{os.pathsep}{path_env}" if path_env else npm_dir
    env.setdefault("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1")
    return profile, env


def _runtime_dependency_checks() -> dict[str, bool]:
    return {
        "uv": _command_exists("uv"),
        "node": _command_exists("node"),
        "npm": _command_exists("npm"),
    }


def _forward_stream_to_stderr(stream: Any, sink: Any, collector: list[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            collector.append(line)
            sink.write(line)
            sink.flush()
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _run_agent_bootstrap(profile: Any, env: dict[str, str]) -> dict[str, Any]:
    report_path = profile.data_dir / "agent_bootstrap_report.json"
    ensure_cmd = [
        "uv",
        "run",
        "python",
        "scripts/agent_manager.py",
        "--ensure",
        "--bootstrap-report-file",
        str(report_path),
    ]
    try:
        proc = subprocess.Popen(
            ensure_cmd,
            cwd=str(_project_root()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            **_windows_subprocess_options(),
        )
    except OSError as exc:
        return {
            "ok": False,
            "exit_code": 127,
            "mode": profile.mode,
            "command": ensure_cmd,
            "bootstrap_report_file": str(report_path),
            "stdout": "",
            "stderr": str(exc),
        }

    if proc.stdout is None or proc.stderr is None:
        return_code = int(proc.wait())
        return {
            "ok": return_code == 0,
            "exit_code": return_code,
            "mode": profile.mode,
            "command": ensure_cmd,
            "bootstrap_report_file": str(report_path),
            "stdout": "",
            "stderr": "",
        }

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    stdout_thread = threading.Thread(
        target=_forward_stream_to_stderr,
        args=(proc.stdout, sys.stderr, stdout_lines),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_forward_stream_to_stderr,
        args=(proc.stderr, sys.stderr, stderr_lines),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    return_code = int(proc.wait())
    stdout_thread.join()
    stderr_thread.join()
    stdout_text = "".join(stdout_lines)
    stderr_text = "".join(stderr_lines)
    return {
        "ok": return_code == 0,
        "exit_code": return_code,
        "mode": profile.mode,
        "command": ensure_cmd,
        "bootstrap_report_file": str(report_path),
        "stdout": stdout_text[-2000:] if stdout_text else "",
        "stderr": stderr_text[-2000:] if stderr_text else "",
    }


def _run_bootstrap_command(
    args: argparse.Namespace,
    *,
    success_message: str,
    failure_message: str,
) -> int:
    profile, env = _runtime_env()
    checks = _runtime_dependency_checks()
    if not all(checks.values()):
        return _emit(
            {
                "ok": False,
                "exit_code": 2,
                "message": "Missing required dependencies.",
                "checks": checks,
            },
            as_json=args.json,
        )
    payload = _run_agent_bootstrap(profile, env)
    payload["checks"] = checks
    payload["message"] = success_message if payload["ok"] else failure_message
    return _emit(payload, as_json=args.json)


def _cmd_install(args: argparse.Namespace) -> int:
    return _run_bootstrap_command(
        args,
        success_message="Install completed.",
        failure_message="Install failed.",
    )


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    return _run_bootstrap_command(
        args,
        success_message="Bootstrap completed.",
        failure_message="Bootstrap failed.",
    )


def _preflight_required_files() -> dict[str, Path]:
    root = _project_root()
    return {
        "api_entry": root / "server" / "main.py",
        "agent_manager": root / "scripts" / "agent_manager.py",
    }


def _preflight_issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(extra)
    return payload


def _integrity_manifest_path() -> Path:
    return _project_root() / INTEGRITY_MANIFEST_NAME


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _run_integrity_checks() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = _integrity_manifest_path()
    check: dict[str, Any] = {
        "path": str(manifest_path),
        "exists": manifest_path.exists(),
        "parse_ok": False,
        "schema_version": None,
        "scope": None,
        "verified_files": 0,
        "missing_files": 0,
        "mismatched_files": 0,
    }
    issues: list[dict[str, Any]] = []
    if not manifest_path.exists():
        issues.append(
            _preflight_issue(
                "integrity_manifest_missing",
                f"Integrity manifest not found: {manifest_path}.",
                path=str(manifest_path),
            )
        )
        return check, issues
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        issues.append(
            _preflight_issue(
                "integrity_manifest_unreadable",
                f"Integrity manifest is unreadable: {manifest_path}.",
                path=str(manifest_path),
            )
        )
        return check, issues
    if not isinstance(manifest_payload, dict):
        issues.append(
            _preflight_issue(
                "integrity_manifest_unreadable",
                "Integrity manifest content is invalid.",
                path=str(manifest_path),
            )
        )
        return check, issues

    files = manifest_payload.get("files")
    if not isinstance(files, list):
        issues.append(
            _preflight_issue(
                "integrity_manifest_unreadable",
                "Integrity manifest missing valid files array.",
                path=str(manifest_path),
            )
        )
        return check, issues

    check["parse_ok"] = True
    check["schema_version"] = manifest_payload.get("schema_version")
    check["scope"] = manifest_payload.get("scope")

    project_root = _project_root()
    for entry in files:
        if not isinstance(entry, dict):
            issues.append(
                _preflight_issue(
                    "integrity_manifest_unreadable",
                    "Integrity manifest entry is invalid.",
                    path=str(manifest_path),
                )
            )
            continue
        rel_path = entry.get("path")
        expected_hash = entry.get("sha256")
        expected_size_raw = entry.get("size")
        if not isinstance(rel_path, str) or not rel_path:
            issues.append(
                _preflight_issue(
                    "integrity_manifest_unreadable",
                    "Integrity manifest entry missing valid path.",
                    path=str(manifest_path),
                )
            )
            continue
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            issues.append(
                _preflight_issue(
                    "integrity_manifest_unreadable",
                    f"Integrity manifest entry missing valid sha256: {rel_path}.",
                    path=str(manifest_path),
                    file=rel_path,
                )
            )
            continue
        expected_size = expected_size_raw if isinstance(expected_size_raw, int) else None
        target = project_root / rel_path
        if not target.is_file():
            check["missing_files"] = int(check["missing_files"]) + 1
            issues.append(
                _preflight_issue(
                    "integrity_file_missing",
                    f"Integrity check file missing: {rel_path}.",
                    file=rel_path,
                    path=str(target),
                )
            )
            continue
        try:
            actual_hash, actual_size = _sha256_file(target)
        except OSError:
            check["missing_files"] = int(check["missing_files"]) + 1
            issues.append(
                _preflight_issue(
                    "integrity_file_missing",
                    f"Integrity check file unreadable: {rel_path}.",
                    file=rel_path,
                    path=str(target),
                )
            )
            continue
        if actual_hash != expected_hash or (expected_size is not None and actual_size != expected_size):
            check["mismatched_files"] = int(check["mismatched_files"]) + 1
            issues.append(
                _preflight_issue(
                    "integrity_hash_mismatch",
                    f"Integrity hash mismatch: {rel_path}.",
                    file=rel_path,
                    expected_sha256=expected_hash,
                    actual_sha256=actual_hash,
                    expected_size=expected_size,
                    actual_size=actual_size,
                )
            )
            continue
        check["verified_files"] = int(check["verified_files"]) + 1
    return check, issues


def _cmd_preflight(args: argparse.Namespace) -> int:
    profile, env = _runtime_env()
    host = str(args.host or env.get("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1"))
    requested_port = int(args.port)
    fallback_span = max(0, int(args.port_fallback_span))
    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    dependency_checks = _runtime_dependency_checks()
    for component, present in dependency_checks.items():
        if not present:
            blocking_issues.append(
                _preflight_issue(
                    "missing_dependency",
                    f"Missing required dependency: {component}.",
                    component=component,
                )
            )

    required_file_checks: dict[str, dict[str, Any]] = {}
    for file_id, path in _preflight_required_files().items():
        exists = path.is_file()
        readable = exists and os.access(path, os.R_OK)
        required_file_checks[file_id] = {
            "path": str(path),
            "exists": exists,
            "readable": readable,
        }
        if not exists:
            blocking_issues.append(
                _preflight_issue(
                    "required_file_missing",
                    f"Required entry file missing: {path}.",
                    file_id=file_id,
                    path=str(path),
                )
            )
        elif not readable:
            blocking_issues.append(
                _preflight_issue(
                    "required_file_unreadable",
                    f"Required entry file is not readable: {path}.",
                    file_id=file_id,
                    path=str(path),
                )
            )

    integrity_check, integrity_issues = _run_integrity_checks()
    blocking_issues.extend(integrity_issues)

    selected_port: int | None = None
    tried_ports: list[int] = []
    if not _is_valid_port(requested_port):
        blocking_issues.append(
            _preflight_issue(
                "invalid_port",
                f"Invalid port: {requested_port}.",
                host=host,
                requested_port=requested_port,
            )
        )
    else:
        selected_port, tried_ports = _select_port_with_fallback(host, requested_port, fallback_span)
        if selected_port is None:
            blocking_issues.append(
                _preflight_issue(
                    "port_unavailable",
                    "No available port found in fallback range.",
                    host=host,
                    requested_port=requested_port,
                    port_fallback_span=fallback_span,
                    tried_ports=tried_ports,
                )
            )

    port_check = {
        "host": host,
        "requested_port": requested_port,
        "port_fallback_span": fallback_span,
        "selected_port": selected_port,
        "tried_ports": tried_ports,
        "available": selected_port is not None,
    }

    bootstrap_report_path = profile.data_dir / "agent_bootstrap_report.json"
    bootstrap_check: dict[str, Any] = {
        "path": str(bootstrap_report_path),
        "exists": bootstrap_report_path.exists(),
        "parse_ok": False,
        "outcome": None,
    }
    if bootstrap_report_path.exists():
        try:
            bootstrap_payload = json.loads(bootstrap_report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            warnings.append(
                _preflight_issue(
                    "bootstrap_report_unreadable",
                    f"Bootstrap report is unreadable: {bootstrap_report_path}.",
                    path=str(bootstrap_report_path),
                )
            )
        else:
            bootstrap_check["parse_ok"] = True
            summary = bootstrap_payload.get("summary") if isinstance(bootstrap_payload, dict) else None
            outcome = str(summary.get("outcome") or "") if isinstance(summary, dict) else ""
            bootstrap_check["outcome"] = outcome or None
            if outcome == "partial_failure":
                warnings.append(
                    _preflight_issue(
                        "bootstrap_partial_failure",
                        "Bootstrap report indicates partial_failure.",
                        path=str(bootstrap_report_path),
                        outcome=outcome,
                    )
                )
    else:
        warnings.append(
            _preflight_issue(
                "bootstrap_report_missing",
                f"Bootstrap report not found: {bootstrap_report_path}.",
                path=str(bootstrap_report_path),
            )
        )

    state_path = _state_file(profile)
    state_exists = state_path.exists()
    state_payload = _load_state(state_path) if state_exists else None
    state_pid = 0
    state_pid_alive = False
    state_stale = False
    if state_exists:
        if state_payload is None:
            state_stale = True
            warnings.append(
                _preflight_issue(
                    "stale_state_file",
                    f"State file exists but is unreadable: {state_path}.",
                    path=str(state_path),
                )
            )
        else:
            try:
                state_pid = int(state_payload.get("pid") or 0)
            except (TypeError, ValueError):
                state_pid = 0
            state_pid_alive = _is_pid_alive(state_pid) if state_pid > 0 else False
            if not state_pid_alive:
                state_stale = True
                warnings.append(
                    _preflight_issue(
                        "stale_state_file",
                        "State file exists but recorded pid is not alive.",
                        path=str(state_path),
                        pid=state_pid if state_pid > 0 else None,
                    )
                )
    state_check = {
        "path": str(state_path),
        "exists": state_exists,
        "parse_ok": (state_payload is not None) if state_exists else True,
        "pid": state_pid if state_pid > 0 else None,
        "pid_alive": state_pid_alive,
        "stale": state_stale,
    }

    has_blocking = bool(blocking_issues)
    if has_blocking:
        severe_codes = {
            "missing_dependency",
            "invalid_port",
            "required_file_missing",
            "required_file_unreadable",
            "integrity_manifest_missing",
            "integrity_manifest_unreadable",
            "integrity_file_missing",
            "integrity_hash_mismatch",
        }
        exit_code = 2 if any(issue.get("code") in severe_codes for issue in blocking_issues) else 1
        ok = False
        message = "Preflight failed with blocking issues."
    else:
        exit_code = 0
        ok = True
        message = "Preflight passed with warnings." if warnings else "Preflight passed."

    suggested_port = selected_port if selected_port is not None else requested_port
    suggested_next = {
        "mode": "local",
        "host": host,
        "requested_port": requested_port,
        "port": suggested_port,
        "port_fallback_span": fallback_span,
        "command": (
            "up --mode local "
            f"--host {host} --port {suggested_port} --port-fallback-span {fallback_span} --json"
        ),
    }

    payload = {
        "ok": ok,
        "exit_code": exit_code,
        "mode": "local",
        "message": message,
        "checks": {
            "dependencies": dependency_checks,
            "required_files": required_file_checks,
            "integrity": integrity_check,
            "port": port_check,
            "bootstrap_report": bootstrap_check,
            "state_file": state_check,
        },
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "suggested_next": suggested_next,
    }
    return _emit(payload, as_json=args.json)


def _collect_local_status(args: argparse.Namespace) -> dict[str, Any]:
    profile, env = _runtime_env()
    state_path = _state_file(profile)
    state = _load_state(state_path) or {}
    host = str(state.get("host") or env.get("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1"))
    port_raw = state.get("port", args.port)
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = int(args.port)
    pid = int(state.get("pid") or 0)
    pid_alive = _is_pid_alive(pid)
    status_code, health_payload = _http_json("GET", _build_service_url(host, port, "/"))
    healthy = status_code == 200 and isinstance(health_payload, dict)
    status = "running" if healthy else ("starting" if pid_alive else "stopped")
    payload = {
        "ok": True,
        "exit_code": 0,
        "mode": "local",
        "status": status,
        "pid": pid if pid > 0 else None,
        "pid_alive": pid_alive,
        "service_healthy": healthy,
        "host": host,
        "port": port,
        "url": _build_service_url(host, port, "/"),
        "state_file": str(state_path),
    }
    payload["message"] = f"Local runtime status: {status}."
    return payload


def _cmd_status_local(args: argparse.Namespace, *, as_json: bool) -> int:
    payload = _collect_local_status(args)
    return _emit(payload, as_json=as_json)


def _cmd_status_docker(args: argparse.Namespace, *, as_json: bool) -> int:
    if not _command_exists("docker"):
        return _emit(
            {
                "ok": False,
                "exit_code": 2,
                "mode": "docker",
                "message": "docker is not installed.",
            },
            as_json=as_json,
        )
    cmd = ["docker", "compose", "ps", "api", "--format", "json"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **_windows_subprocess_options(),
    )
    raw = (proc.stdout or "").strip()
    status = "unknown"
    detail: dict[str, Any] | str = raw
    if proc.returncode == 0 and raw:
        try:
            parsed = json.loads(raw)
            detail = parsed
            service_state = str(parsed.get("State") or parsed.get("Status") or "").lower()
            status = "running" if "running" in service_state else "stopped"
        except json.JSONDecodeError:
            status = "running" if "running" in raw.lower() else "stopped"
    payload = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "mode": "docker",
        "status": status,
        "detail": detail,
        "message": f"Docker runtime status: {status}.",
    }
    if proc.returncode != 0:
        payload["stderr"] = proc.stderr[-2000:] if proc.stderr else ""
    return _emit(payload, as_json=as_json)


def _cmd_status(args: argparse.Namespace) -> int:
    if args.mode == "docker":
        return _cmd_status_docker(args, as_json=args.json)
    return _cmd_status_local(args, as_json=args.json)


def _start_local_process(host: str, port: int, env: dict[str, str], profile) -> tuple[int, Path]:
    project_root = _project_root()
    log_path = _local_logs_file(profile)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")
    cmd = ["uv", "run", "uvicorn", "server.main:app", "--host", host, "--port", str(port)]
    kwargs: dict[str, Any] = {
        "cwd": str(project_root),
        "env": env,
        "stdout": log_file,
        "stderr": log_file,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform.startswith("win"):
        kwargs.update(_windows_subprocess_options(detached=True))
    else:
        kwargs["preexec_fn"] = os.setsid
    proc = subprocess.Popen(cmd, **kwargs)
    log_file.close()
    return int(proc.pid or 0), log_path


def _cmd_up_local(args: argparse.Namespace) -> int:
    profile, env = _runtime_env()
    if not _command_exists("uv"):
        return _emit(
            {"ok": False, "exit_code": 2, "message": "uv is not installed."},
            as_json=args.json,
        )
    current = _collect_local_status(args)
    if bool(current.get("service_healthy")):
        return _emit(
            {
                "ok": True,
                "exit_code": 0,
                "message": "Local runtime already running.",
                "mode": "local",
                "host": current.get("host"),
                "port": current.get("port"),
                "url": current.get("url"),
            },
            as_json=args.json,
        )
    host = str(args.host or env.get("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1"))
    requested_port = int(args.port)
    if not _is_valid_port(requested_port):
        return _emit(
            {
                "ok": False,
                "exit_code": 2,
                "mode": "local",
                "message": f"Invalid port: {requested_port}.",
            },
            as_json=args.json,
        )
    fallback_span = max(0, int(args.port_fallback_span))
    selected_port, tried_ports = _select_port_with_fallback(host, requested_port, fallback_span)
    if selected_port is None:
        return _emit(
            {
                "ok": False,
                "exit_code": 1,
                "mode": "local",
                "message": "No available port found in fallback range.",
                "host": host,
                "requested_port": requested_port,
                "port_fallback_span": fallback_span,
                "tried_ports": tried_ports,
            },
            as_json=args.json,
        )
    fallback_used = selected_port != requested_port
    pid, log_path = _start_local_process(host, selected_port, env, profile)
    if pid <= 0:
        return _emit(
            {"ok": False, "exit_code": 1, "message": "Failed to start local runtime."},
            as_json=args.json,
        )
    state_path = _state_file(profile)
    _save_state(
        state_path,
        {
            "pid": pid,
            "host": host,
            "port": selected_port,
            "started_at": _utc_now_iso(),
            "mode": "local",
            "log_path": str(log_path),
        },
    )
    deadline = time.monotonic() + float(args.wait_seconds)
    healthy = False
    while time.monotonic() < deadline:
        code, _ = _http_json("GET", _build_service_url(host, selected_port, "/"), timeout=1.5)
        if code == 200:
            healthy = True
            break
        if not _is_pid_alive(pid):
            break
        time.sleep(0.5)
    if not healthy:
        _terminate_pid(pid)
        _remove_state(state_path)
        return _emit(
            {
                "ok": False,
                "exit_code": 1,
                "message": "Local runtime failed to become healthy within timeout.",
                "pid": pid,
                "log_path": str(log_path),
                "host": host,
                "requested_port": requested_port,
                "port": selected_port,
                "port_fallback_span": fallback_span,
                "port_fallback_used": fallback_used,
                "tried_ports": tried_ports,
            },
            as_json=args.json,
        )
    started_message = "Local runtime started."
    if fallback_used:
        started_message = (
            f"Local runtime started on fallback port {selected_port} "
            f"(requested {requested_port})."
        )
    return _emit(
        {
            "ok": True,
            "exit_code": 0,
            "message": started_message,
            "mode": "local",
            "pid": pid,
            "host": host,
            "requested_port": requested_port,
            "port": selected_port,
            "port_fallback_span": fallback_span,
            "port_fallback_used": fallback_used,
            "tried_ports": tried_ports,
            "url": _build_service_url(host, selected_port, "/"),
            "log_path": str(log_path),
        },
        as_json=args.json,
    )


def _cmd_up_docker(args: argparse.Namespace) -> int:
    if not _command_exists("docker"):
        return _emit(
            {"ok": False, "exit_code": 2, "message": "docker is not installed."},
            as_json=args.json,
        )
    cmd = ["docker", "compose", "up", "-d", "api"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **_windows_subprocess_options(),
    )
    return _emit(
        {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "mode": "docker",
            "message": "Docker api service started." if proc.returncode == 0 else "Docker start failed.",
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        },
        as_json=args.json,
    )


def _cmd_up(args: argparse.Namespace) -> int:
    if args.mode == "docker":
        return _cmd_up_docker(args)
    return _cmd_up_local(args)


def _cmd_down_local(args: argparse.Namespace) -> int:
    profile, _ = _runtime_env()
    state_path = _state_file(profile)
    state = _load_state(state_path) or {}
    pid = int(state.get("pid") or 0)
    if pid > 0 and _is_pid_alive(pid):
        _terminate_pid(pid)
    _remove_state(state_path)
    return _emit(
        {"ok": True, "exit_code": 0, "mode": "local", "message": "Local runtime stopped."},
        as_json=args.json,
    )


def _cmd_down_docker(args: argparse.Namespace) -> int:
    if not _command_exists("docker"):
        return _emit(
            {"ok": False, "exit_code": 2, "message": "docker is not installed."},
            as_json=args.json,
        )
    cmd = ["docker", "compose", "stop", "api"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **_windows_subprocess_options(),
    )
    return _emit(
        {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "mode": "docker",
            "message": "Docker api service stopped." if proc.returncode == 0 else "Docker stop failed.",
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        },
        as_json=args.json,
    )


def _cmd_down(args: argparse.Namespace) -> int:
    if args.mode == "docker":
        return _cmd_down_docker(args)
    return _cmd_down_local(args)


def _cmd_doctor(args: argparse.Namespace) -> int:
    profile, env = _runtime_env()
    checks = {
        "uv": _command_exists("uv"),
        "node": _command_exists("node"),
        "npm": _command_exists("npm"),
        "docker": _command_exists("docker"),
        "ttyd": _command_exists("ttyd"),
    }
    payload = {
        "ok": True,
        "exit_code": 0,
        "mode": profile.mode,
        "checks": checks,
        "paths": {
            "data_dir": str(profile.data_dir),
            "agent_cache_root": str(profile.agent_cache_root),
            "agent_home": str(profile.agent_home),
            "npm_prefix": str(profile.npm_prefix),
            "uv_cache_dir": str(profile.uv_cache_dir),
            "uv_project_environment": str(profile.uv_project_environment),
            "state_file": str(_state_file(profile)),
            "local_log_file": str(_local_logs_file(profile)),
        },
        "env_snapshot": {
            "SKILL_RUNNER_RUNTIME_MODE": env.get("SKILL_RUNNER_RUNTIME_MODE"),
            "SKILL_RUNNER_LOCAL_BIND_HOST": env.get("SKILL_RUNNER_LOCAL_BIND_HOST"),
            "SKILL_RUNNER_LOCAL_PORT": os.environ.get("SKILL_RUNNER_LOCAL_PORT"),
            "SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN": os.environ.get("SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN"),
        },
        "message": "Doctor completed.",
    }
    return _emit(payload, as_json=args.json)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Skill Runner control utility")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="Install/ensure local runtime prerequisites")
    install.add_argument("--json", action="store_true", help="Output JSON")
    install.set_defaults(func=_cmd_install)

    up = sub.add_parser("up", help="Start runtime")
    up.add_argument("--mode", choices=("local", "docker"), default="local")
    up.add_argument("--host", default=os.environ.get("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1"))
    up.add_argument("--port", type=int, default=_default_ctl_port())
    up.add_argument("--port-fallback-span", type=int, default=_default_ctl_fallback_span())
    up.add_argument("--wait-seconds", type=int, default=30)
    up.add_argument("--json", action="store_true", help="Output JSON")
    up.set_defaults(func=_cmd_up)

    down = sub.add_parser("down", help="Stop runtime")
    down.add_argument("--mode", choices=("local", "docker"), default="local")
    down.add_argument("--json", action="store_true", help="Output JSON")
    down.set_defaults(func=_cmd_down)

    status = sub.add_parser("status", help="Get runtime status")
    status.add_argument("--mode", choices=("local", "docker"), default="local")
    status.add_argument("--port", type=int, default=_default_ctl_port())
    status.add_argument("--json", action="store_true", help="Output JSON")
    status.set_defaults(func=_cmd_status)

    preflight = sub.add_parser("preflight", help="Run static local-runtime preflight checks")
    preflight.add_argument("--host", default=os.environ.get("SKILL_RUNNER_LOCAL_BIND_HOST", "127.0.0.1"))
    preflight.add_argument("--port", type=int, default=_default_ctl_port())
    preflight.add_argument("--port-fallback-span", type=int, default=_default_ctl_fallback_span())
    preflight.add_argument("--json", action="store_true", help="Output JSON")
    preflight.set_defaults(func=_cmd_preflight)

    doctor = sub.add_parser("doctor", help="Diagnose runtime environment")
    doctor.add_argument("--json", action="store_true", help="Output JSON")
    doctor.set_defaults(func=_cmd_doctor)

    bootstrap = sub.add_parser("bootstrap", help="Run startup bootstrap (same strategy as ensure)")
    bootstrap.add_argument("--json", action="store_true", help="Output JSON")
    bootstrap.set_defaults(func=_cmd_bootstrap)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
