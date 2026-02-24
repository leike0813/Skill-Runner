from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import logging

from server.models import EngineSessionHandle, EngineSessionHandleType
from server.models import SkillManifest
from server.services.engine_adapter_registry import engine_adapter_registry
from server.services.run_folder_trust_manager import run_folder_trust_manager
from server.services.runtime_event_protocol import (
    build_fcmp_events,
    build_rasp_events,
    compute_protocol_metrics,
    write_jsonl,
)

from .config import HarnessConfig
from .errors import HarnessError
from .skill_injection import inject_all_skill_packages
from .storage import (
    AttemptPaths,
    assign_handle,
    diff_snapshot,
    load_handle_metadata,
    resolve_next_attempt_paths,
    resolve_or_create_run_dir,
    snapshot_filesystem,
)


SUPPORTED_ENGINES = {"codex", "gemini", "iflow", "opencode"}
TRUST_ENGINES = {"codex", "gemini"}
HARNESS_CODEX_PROFILE_NAME = "skill-runner-harness"
HARNESS_CODEX_DEFAULT_MODEL = "gpt-5.1-codex-mini"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HarnessLaunchRequest:
    engine: str
    passthrough_args: list[str]
    translate_level: int
    run_selector: str | None = None


@dataclass(frozen=True)
class HarnessResumeRequest:
    handle: str
    message: str
    translate_level: int | None = None


class HarnessRuntime:
    def __init__(self, config: HarnessConfig) -> None:
        self.config = config

    def _ensure_engine_supported(self, engine: str) -> str:
        normalized = engine.strip().lower()
        if normalized not in SUPPORTED_ENGINES:
            raise HarnessError(
                "ENGINE_UNSUPPORTED",
                f'Unsupported engine "{engine}"',
                details={"engine": engine, "supported_engines": sorted(SUPPORTED_ENGINES)},
            )
        return normalized

    def _map_runtime_error(self, *, engine: str, exc: Exception) -> HarnessError:
        message = str(exc)
        if "ENGINE_CAPABILITY_UNAVAILABLE" in message:
            raise HarnessError(
                "ENGINE_CAPABILITY_UNAVAILABLE",
                "Engine capability is unavailable in current backend runtime",
                details={
                    "engine": engine,
                    "capability": "adapter.execute",
                    "reason": message,
                },
            )
        raise HarnessError(
            "ENGINE_COMMAND_BUILD_FAILED",
            f"Failed to build command for {engine}",
            details={"engine": engine, "reason": message},
        )

    def _resolve_adapter(self, engine: str):
        adapter = engine_adapter_registry.get(engine)
        if adapter is None:
            raise HarnessError(
                "ENGINE_UNSUPPORTED",
                f'Unsupported engine "{engine}"',
                details={"engine": engine, "supported_engines": sorted(SUPPORTED_ENGINES)},
            )
        return adapter

    def _ensure_executable_path(self, *, engine: str, command: list[str]) -> Path:
        if not command:
            raise HarnessError(
                "ENGINE_COMMAND_BUILD_FAILED",
                f"Failed to build command for {engine}",
                details={"engine": engine, "reason": "empty command"},
            )
        executable = Path(command[0])
        if not executable.is_absolute():
            return executable
        if not executable.exists() or not os.access(executable, os.X_OK):
            raise HarnessError(
                "ENGINE_EXECUTABLE_NOT_EXECUTABLE",
                f"Resolved executable is not runnable for {engine}",
                details={"engine": engine, "path": str(executable)},
            )
        return executable

    def _check_environment(self, engine: str, executable: Path) -> dict[str, Any]:
        profile = self.config.runtime_profile
        return {
            "engine": engine,
            "executable": str(executable),
            "runtime_mode": profile.mode,
            "data_dir": str(profile.data_dir),
            "run_root": str(self.config.run_root),
            "agent_cache_dir": str(profile.agent_cache_root),
            "agent_home": str(profile.agent_home),
            "npm_prefix": str(profile.npm_prefix),
            "uv_cache_dir": str(profile.uv_cache_dir),
            "uv_project_environment": str(profile.uv_project_environment),
            "managed_bin_dirs": [str(item) for item in profile.managed_bin_dirs],
        }

    def _resolve_config_roots(self, engine: str) -> list[str]:
        profile = self.config.runtime_profile
        env = profile.build_subprocess_env(os.environ.copy())
        roots: list[str] = []
        for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
            value = env.get(key)
            if isinstance(value, str) and value.strip():
                roots.append(value.strip())
        home = env.get("HOME")
        if isinstance(home, str) and home.strip():
            home_value = home.strip()
            roots.append(home_value)
            engine_dirs = {
                "codex": ".codex",
                "gemini": ".gemini",
                "iflow": ".iflow",
                "opencode": ".opencode",
            }
            mapped = engine_dirs.get(engine)
            if mapped:
                roots.append(str(Path(home_value) / mapped))
        deduped: list[str] = []
        seen: set[str] = set()
        for item in roots:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _resolve_project_root(self) -> Path:
        configured = self.config.project_root
        if isinstance(configured, Path):
            return configured.resolve()
        return self.config.run_root.parent.resolve()

    def _inject_engine_tool_config(
        self,
        *,
        engine: str,
        adapter: Any,
        run_dir: Path,
    ) -> dict[str, Any]:
        skill = SkillManifest(id="harness-config-bootstrap", path=None)
        options: dict[str, Any] = {"__harness_mode": True}
        if engine == "codex":
            options["__codex_profile_name"] = HARNESS_CODEX_PROFILE_NAME
            options["model"] = HARNESS_CODEX_DEFAULT_MODEL
        try:
            config_path_obj = adapter._construct_config(skill, run_dir, options)
        except Exception as exc:
            raise HarnessError(
                "ENGINE_CONFIG_INJECTION_FAILED",
                f"Failed to inject {engine} tool config",
                details={"engine": engine, "reason": str(exc)},
            ) from exc
        config_path = str(config_path_obj) if config_path_obj is not None else ""
        profile_name_obj = options.get("__codex_profile_name")
        profile_name = (
            profile_name_obj.strip()
            if isinstance(profile_name_obj, str) and profile_name_obj.strip()
            else None
        )
        return {
            "engine": engine,
            "config_path": config_path,
            "profile_name": profile_name,
        }

    def start(self, request: HarnessLaunchRequest) -> dict[str, Any]:
        engine = self._ensure_engine_supported(request.engine)
        adapter = self._resolve_adapter(engine)
        try:
            command = adapter.build_start_command(
                prompt="",
                options={"__harness_mode": True},
                passthrough_args=list(request.passthrough_args),
                use_profile_defaults=False,
            )
        except Exception as exc:  # pragma: no cover - mapped in tests by error code
            raise self._map_runtime_error(engine=engine, exc=exc)
        self._ensure_executable_path(engine=engine, command=command)
        run_dir = resolve_or_create_run_dir(self.config.run_root, engine, request.run_selector)
        return self._execute_attempt(
            run_dir=run_dir,
            engine=engine,
            translate_level=request.translate_level,
            command=command,
            launch_kind="start",
            launch_payload={
                "passthrough_args": list(request.passthrough_args),
                "run_selector": request.run_selector,
            },
            stdin_text="",
            session_handle_hint=None,
        )

    def resume(self, request: HarnessResumeRequest) -> dict[str, Any]:
        record = load_handle_metadata(self.config.run_root, request.handle)
        engine_obj = record.get("engine")
        if not isinstance(engine_obj, str) or not engine_obj.strip():
            raise HarnessError(
                "HANDLE_METADATA_INVALID",
                "Handle metadata does not contain engine information",
                details={"handle": request.handle},
            )
        engine = self._ensure_engine_supported(engine_obj)
        adapter = self._resolve_adapter(engine)
        session_id_obj = record.get("session_id")
        if not isinstance(session_id_obj, str) or not session_id_obj.strip():
            raise HarnessError(
                "SESSION_RESUME_FAILED",
                "resume requires a detected session id in handle metadata",
                details={"handle": request.handle},
            )
        run_dir_name_obj = record.get("run_dir")
        run_dir = (
            (self.config.run_root / str(run_dir_name_obj)).resolve()
            if isinstance(run_dir_name_obj, str)
            else None
        )
        if run_dir is None or not run_dir.exists():
            raise HarnessError(
                "RUN_DIRECTORY_MISSING",
                "run directory referenced by handle does not exist",
                details={"handle": request.handle, "run_dir": str(run_dir)},
            )

        stored_args_obj = record.get("passthrough_args")
        stored_args = (
            [str(item) for item in stored_args_obj]
            if isinstance(stored_args_obj, list)
            else []
        )
        if not request.message.strip():
            raise HarnessError("INVALID_RESUME_MESSAGE", "resume requires a non-empty <message>")
        try:
            command = adapter.build_resume_command(
                prompt=request.message,
                options={"__harness_mode": True},
                session_handle=EngineSessionHandle(
                    engine=engine,
                    handle_type=EngineSessionHandleType.SESSION_ID,
                    handle_value=session_id_obj.strip(),
                    created_at_turn=1,
                ),
                passthrough_args=stored_args,
                use_profile_defaults=False,
            )
        except Exception as exc:  # pragma: no cover - mapped in tests by error code
            raise self._map_runtime_error(engine=engine, exc=exc)
        self._ensure_executable_path(engine=engine, command=command)
        translate_level = (
            request.translate_level
            if request.translate_level is not None
            else int(record.get("translate_level", 0))
        )
        return self._execute_attempt(
            run_dir=run_dir,
            engine=engine,
            translate_level=translate_level,
            command=command,
            launch_kind="resume",
            launch_payload={"handle": record.get("handle"), "message": request.message},
            stdin_text=f"{request.message}\n",
            session_handle_hint=str(record.get("handle", request.handle)),
        )

    def _run_command(
        self,
        *,
        engine: str,
        command: list[str],
        run_dir: Path,
        translate_level: int = 0,
        attempt_paths: AttemptPaths | None = None,
        stdin_text: str = "",
    ) -> tuple[int, str, str, str]:
        env = self.config.runtime_profile.build_subprocess_env(os.environ.copy())
        script_bin = shutil.which("script", path=env.get("PATH"))
        if not script_bin:
            raise HarnessError(
                "PTY_RUNTIME_UNAVAILABLE",
                'Required command "script" is unavailable; harness requires PTY runtime',
                details={"command": "script"},
            )
        script_args = [script_bin, "-qef"]
        has_log_output = False
        if attempt_paths is not None:
            script_args.extend(["--log-in", str(attempt_paths.stdin)])
            script_args.extend(["--log-out", str(attempt_paths.pty_output)])
            has_log_output = True
        script_args.extend(["--command", shlex.join(command)])
        if not has_log_output:
            script_args.append("/dev/null")

        interactive_passthrough = (
            translate_level == 0
            and sys.stdin.isatty()
            and sys.stdout.isatty()
            and sys.stderr.isatty()
        )
        if interactive_passthrough:
            interactive_result = subprocess.run(
                script_args,
                cwd=str(run_dir),
                env=env,
                text=True,
                check=False,
            )
            pty_text = ""
            if attempt_paths is not None and attempt_paths.pty_output.exists():
                pty_text = attempt_paths.pty_output.read_text(encoding="utf-8", errors="replace")
            stdin_captured = ""
            if attempt_paths is not None and attempt_paths.stdin.exists():
                stdin_captured = attempt_paths.stdin.read_text(encoding="utf-8", errors="replace")
            return interactive_result.returncode, pty_text, "", stdin_captured

        run_input = stdin_text if stdin_text else None
        wrapped_command = [
            *script_args,
        ]
        run_result = subprocess.run(
            wrapped_command,
            cwd=str(run_dir),
            env=env,
            capture_output=True,
            text=True,
            input=run_input,
            check=False,
        )
        pty_text = ""
        if attempt_paths is not None and attempt_paths.pty_output.exists():
            pty_text = attempt_paths.pty_output.read_text(encoding="utf-8", errors="replace")
        if not pty_text:
            pty_text = run_result.stdout or ""
        stdin_captured = ""
        if attempt_paths is not None and attempt_paths.stdin.exists():
            stdin_captured = attempt_paths.stdin.read_text(encoding="utf-8", errors="replace")
        elif stdin_text:
            stdin_captured = stdin_text
        stdout_text = run_result.stdout or pty_text
        stderr_text = run_result.stderr or ""
        return run_result.returncode, stdout_text, stderr_text, stdin_captured

    def _execute_attempt(
        self,
        *,
        run_dir: Path,
        engine: str,
        translate_level: int,
        command: list[str],
        launch_kind: str,
        launch_payload: dict[str, Any],
        stdin_text: str,
        session_handle_hint: str | None,
    ) -> dict[str, Any]:
        if translate_level not in {0, 1, 2, 3}:
            raise HarnessError(
                "INVALID_TRANSLATE_LEVEL",
                f'Invalid translate level "{translate_level}"',
                details={"translate_level": translate_level, "allowed": [0, 1, 2, 3]},
            )
        run_dir.mkdir(parents=True, exist_ok=True)
        adapter = self._resolve_adapter(engine)
        config_injection = self._inject_engine_tool_config(
            engine=engine,
            adapter=adapter,
            run_dir=run_dir,
        )
        project_root = self._resolve_project_root()
        skill_injection = inject_all_skill_packages(
            project_root=project_root,
            run_directory=run_dir,
            engine=engine,
        )
        prefix = f"[agent:{engine}]"
        passthrough_args = launch_payload.get("passthrough_args")
        if isinstance(passthrough_args, list):
            passthrough = [str(item) for item in passthrough_args]
        else:
            passthrough = []
        config_roots = self._resolve_config_roots(engine)
        attempt_paths = resolve_next_attempt_paths(run_dir)
        launch_payload_with_injection = dict(launch_payload)
        launch_payload_with_injection["skill_injection"] = skill_injection
        sys.stderr.write(f"{prefix} run_id={run_dir.name}\n")
        sys.stderr.write(f"{prefix} run_dir={run_dir}\n")
        sys.stderr.write(f"{prefix} executable={command[0] if command else ''}\n")
        sys.stderr.write(f"{prefix} passthrough={json.dumps(passthrough, ensure_ascii=False)}\n")
        sys.stderr.write(f"{prefix} translate_mode={translate_level}\n")
        sys.stderr.write(
            f"{prefix} injected_skills={int(skill_injection.get('skill_count', 0))} "
            f"target_root={skill_injection.get('target_root') or '(unsupported-agent)'}\n"
        )
        sys.stderr.write(f"{prefix} config_roots={','.join(config_roots)}\n")
        sys.stderr.write(f"{prefix} ---------------- runtime begin ----------------\n")
        try:
            before_snapshot = snapshot_filesystem(run_dir)
            trust_registered = False
            try:
                if engine in TRUST_ENGINES:
                    run_folder_trust_manager.register_run_folder(engine, run_dir)
                    trust_registered = True
                exit_code, stdout_text, stderr_text, stdin_captured = self._run_command(
                    engine=engine,
                    command=command,
                    run_dir=run_dir,
                    translate_level=translate_level,
                    attempt_paths=attempt_paths,
                    stdin_text=stdin_text,
                )
            finally:
                if trust_registered:
                    try:
                        run_folder_trust_manager.remove_run_folder(engine, run_dir)
                    except Exception:
                        logger.warning(
                            "Failed to cleanup harness run folder trust for engine=%s run_id=%s",
                            engine,
                            run_dir.name,
                            exc_info=True,
                        )
            if not attempt_paths.stdin.exists():
                attempt_paths.stdin.write_text(stdin_captured or stdin_text, encoding="utf-8")
            pty_text = (
                attempt_paths.pty_output.read_text(encoding="utf-8", errors="replace")
                if attempt_paths.pty_output.exists()
                else (stdout_text if not stderr_text else f"{stdout_text}\n{stderr_text}")
            )
            attempt_paths.stdout.write_text(stdout_text, encoding="utf-8")
            attempt_paths.stderr.write_text(stderr_text, encoding="utf-8")
            if not attempt_paths.pty_output.exists():
                attempt_paths.pty_output.write_text(pty_text, encoding="utf-8")

            after_snapshot = snapshot_filesystem(run_dir)
            diff_payload = diff_snapshot(before_snapshot, after_snapshot)
            attempt_paths.fs_before.write_text(
                json.dumps(before_snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            attempt_paths.fs_after.write_text(
                json.dumps(after_snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            attempt_paths.fs_diff.write_text(
                json.dumps(diff_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            done_marker_found = (
                "__SKILL_DONE__" in stdout_text
                or "__SKILL_DONE__" in stderr_text
                or "__SKILL_DONE__" in pty_text
            )
            completion_payload = self._build_completion_payload(
                exit_code=exit_code,
                done_marker_found=done_marker_found,
            )
            status = self._status_from_completion(completion_payload["state"])

            parsed = adapter.parse_runtime_stream(
                stdout_raw=stdout_text.encode("utf-8"),
                stderr_raw=stderr_text.encode("utf-8"),
                pty_raw=pty_text.encode("utf-8"),
            )
            session_id = parsed.get("session_id") if isinstance(parsed.get("session_id"), str) else None
            pending_interaction = (
                {"interaction_id": attempt_paths.attempt_number, "prompt": "Provide next user turn"}
                if status == "waiting_user"
                else None
            )
            rasp_models = build_rasp_events(
                run_id=run_dir.name,
                engine=engine,
                attempt_number=attempt_paths.attempt_number,
                status=status,
                pending_interaction=pending_interaction,
                stdout_path=attempt_paths.stdout,
                stderr_path=attempt_paths.stderr,
                pty_path=attempt_paths.pty_output,
                completion=completion_payload,
            )
            fcmp_models = build_fcmp_events(rasp_models)
            rasp_rows = [item.model_dump(mode="json") for item in rasp_models]
            fcmp_rows = [item.model_dump(mode="json") for item in fcmp_models]
            write_jsonl(attempt_paths.rasp_events, rasp_rows)
            write_jsonl(attempt_paths.fcmp_events, fcmp_rows)
            write_jsonl(
                attempt_paths.parser_diagnostics,
                [
                    row
                    for row in rasp_rows
                    if isinstance(row.get("event"), dict)
                    and row["event"].get("category") == "diagnostic"
                ],
            )
            metrics = compute_protocol_metrics(rasp_models)
            attempt_paths.protocol_metrics.write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            report = self._build_conformance_report(
                engine=engine,
                translate_level=translate_level,
                attempt_number=attempt_paths.attempt_number,
                launch_kind=launch_kind,
                completion=completion_payload,
                metrics=metrics,
                fcmp_rows=fcmp_rows,
                diagnostics=list(parsed.get("diagnostics", [])),
            )
            attempt_paths.conformance_report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            handle: str | None = session_handle_hint
            if session_id:
                metadata = {
                    "engine": engine,
                    "run_id": run_dir.name,
                    "run_dir": run_dir.name,
                    "session_id": session_id,
                    "translate_level": translate_level,
                    "passthrough_args": list(launch_payload.get("passthrough_args", [])),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                handle = assign_handle(
                    self.config.run_root,
                    run_dir.name,
                    metadata,
                    preferred_handle=session_handle_hint,
                )

            meta_payload: dict[str, Any] = {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "attempt": {"number": attempt_paths.attempt_number},
                "engine": engine,
                "status": status,
                "completion": completion_payload,
                "launch": {
                    "kind": launch_kind,
                    "command": command,
                    "payload": launch_payload_with_injection,
                    "translate_level": translate_level,
                },
                "environment": self._check_environment(engine, Path(command[0])),
                "audit_files": {
                    "meta": attempt_paths.meta.name,
                    "stdin": attempt_paths.stdin.name,
                    "stdout": attempt_paths.stdout.name,
                    "stderr": attempt_paths.stderr.name,
                    "pty_output": attempt_paths.pty_output.name,
                    "fs_before": attempt_paths.fs_before.name,
                    "fs_after": attempt_paths.fs_after.name,
                    "fs_diff": attempt_paths.fs_diff.name,
                    "rasp_events": attempt_paths.rasp_events.name,
                    "fcmp_events": attempt_paths.fcmp_events.name,
                    "parser_diagnostics": attempt_paths.parser_diagnostics.name,
                    "protocol_metrics": attempt_paths.protocol_metrics.name,
                    "conformance_report": attempt_paths.conformance_report.name,
                },
                "handle": handle,
                "session_id": session_id,
                "started_at": datetime.utcnow().isoformat(),
                "finished_at": datetime.utcnow().isoformat(),
                "exit_code": exit_code,
                "skill_injection": skill_injection,
                "config_injection": config_injection,
            }
            attempt_paths.meta.write_text(
                json.dumps(meta_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            view = self._render_translate_view(
                translate_level=translate_level,
                stdout=stdout_text,
                stderr=stderr_text,
                parsed=parsed,
                fcmp_rows=fcmp_rows,
                report=report,
            )
            if translate_level > 0:
                self._emit_translate_view(view)
            return {
                "ok": True,
                "engine": engine,
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "attempt_number": attempt_paths.attempt_number,
                "status": status,
                "translate_level": translate_level,
                "handle": handle,
                "session_id": session_id,
                "exit_code": exit_code,
                "completion": completion_payload,
                "view": view,
                "audit": {
                    "meta": str(attempt_paths.meta),
                    "report": str(attempt_paths.conformance_report),
                    "rasp_events": str(attempt_paths.rasp_events),
                    "fcmp_events": str(attempt_paths.fcmp_events),
                    "fs_diff": str(attempt_paths.fs_diff),
                },
            }
        finally:
            sys.stderr.write(f"[agent:{engine}] ---------------- runtime end ----------------\n")

    def _emit_translate_view(self, view: Any) -> None:
        if view is None:
            return
        if isinstance(view, str):
            text = view
        else:
            text = json.dumps(view, ensure_ascii=False, indent=2)
        if text and not text.endswith("\n"):
            text = f"{text}\n"
        if text:
            sys.stdout.write(text)

    def _build_completion_payload(self, *, exit_code: int, done_marker_found: bool) -> dict[str, Any]:
        diagnostics: list[str] = []
        if exit_code == 0 and done_marker_found:
            state = "completed"
            reason_code = "DONE_MARKER_FOUND"
        elif exit_code == 0:
            state = "awaiting_user_input"
            reason_code = "WAITING_USER_INPUT"
        else:
            state = "interrupted"
            reason_code = "NON_ZERO_EXIT"
            if done_marker_found:
                diagnostics.append("DONE_MARKER_WITH_NON_ZERO_EXIT")
        return {
            "state": state,
            "reason_code": reason_code,
            "exit_code": exit_code,
            "diagnostics": diagnostics,
        }

    def _status_from_completion(self, state: str) -> str:
        if state == "completed":
            return "succeeded"
        if state == "awaiting_user_input":
            return "waiting_user"
        return "failed"

    def _build_conformance_report(
        self,
        *,
        engine: str,
        translate_level: int,
        attempt_number: int,
        launch_kind: str,
        completion: dict[str, Any],
        metrics: dict[str, Any],
        fcmp_rows: list[dict[str, Any]],
        diagnostics: list[str],
    ) -> dict[str, Any]:
        fcmp_types: list[str] = []
        fcmp_diagnostics: list[str] = []
        assistant_count = 0
        for row in fcmp_rows:
            type_name = row.get("type")
            if isinstance(type_name, str) and type_name not in fcmp_types:
                fcmp_types.append(type_name)
            if type_name == "assistant.message.final":
                assistant_count += 1
            if type_name == "diagnostic.warning":
                data_obj = row.get("data")
                if isinstance(data_obj, dict):
                    code = data_obj.get("code")
                    if isinstance(code, str) and code:
                        fcmp_diagnostics.append(code)
        return {
            "engine": engine,
            "attempt_number": attempt_number,
            "launch_kind": launch_kind,
            "translate_level": translate_level,
            "parser_profile": metrics.get("parser_profile"),
            "fcmp_summary": {
                "event_count": len(fcmp_rows),
                "assistant_message_count": assistant_count,
                "event_types": fcmp_types,
            },
            "diagnostics": sorted(set(diagnostics + fcmp_diagnostics)),
            "completion": {
                "state": completion.get("state"),
                "reason_code": completion.get("reason_code"),
            },
            "metrics": metrics,
        }

    def _render_translate_view(
        self,
        *,
        translate_level: int,
        stdout: str,
        stderr: str,
        parsed: dict[str, Any],
        fcmp_rows: list[dict[str, Any]],
        report: dict[str, Any],
    ) -> Any:
        if translate_level == 0:
            return {"stdout": stdout, "stderr": stderr}
        if translate_level == 1:
            return {
                "parser": parsed.get("parser"),
                "confidence": parsed.get("confidence"),
                "session_id": parsed.get("session_id"),
                "assistant_messages": parsed.get("assistant_messages"),
                "diagnostics": parsed.get("diagnostics"),
            }
        if translate_level == 2:
            return {"fcmp_events": fcmp_rows}
        completion_obj = report.get("completion")
        completion_state = (
            completion_obj.get("state")
            if isinstance(completion_obj, dict)
            else None
        )
        lines = self._build_frontend_markdown_lines(
            parsed=parsed,
            fcmp_rows=fcmp_rows,
            completion_state=completion_state if isinstance(completion_state, str) else "",
        )
        return "\n".join(
            [
                "### Simulated Frontend View (Markdown)",
                *[f"- {line}" for line in lines],
                "",
            ]
        )

    def _build_frontend_markdown_lines(
        self,
        *,
        parsed: dict[str, Any],
        fcmp_rows: list[dict[str, Any]],
        completion_state: str,
    ) -> list[str]:
        lines: list[str] = []
        for row in fcmp_rows:
            if not isinstance(row, dict):
                continue
            row_type = row.get("type")
            data_obj = row.get("data")
            data = data_obj if isinstance(data_obj, dict) else {}
            if row_type == "assistant.message.final":
                text = data.get("text")
                if isinstance(text, str) and text.strip():
                    lines.append(f"Assistant: {text.strip()}")
                continue
            if row_type == "user.input.required":
                prompt = data.get("prompt")
                if isinstance(prompt, str):
                    normalized_prompt = prompt.strip()
                    if normalized_prompt and normalized_prompt.lower() not in {
                        "provide next user turn",
                        "provide next user turn.",
                    }:
                        lines.append(f"System: {normalized_prompt}")
                lines.append("System: (请输入下一步指令...)")
                continue
            if row_type == "conversation.completed":
                lines.append("System: 任务完成")
                continue
            if row_type == "conversation.failed":
                lines.append("System: 任务执行失败")
        if not lines:
            assistant_obj = parsed.get("assistant_messages")
            if isinstance(assistant_obj, list):
                for item in assistant_obj:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            lines.append(f"Assistant: {text.strip()}")
        if not lines:
            if completion_state == "awaiting_user_input":
                lines.append("System: (请输入下一步指令...)")
            elif completion_state == "completed":
                lines.append("System: 任务完成")
            elif completion_state == "interrupted":
                lines.append("System: 任务执行失败")
        if not lines:
            lines.append("(无可展示的前端对话文本)")
        return lines
