from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, cast

from ...config import config
from ...models import (
    AdapterTurnInteraction,
    AdapterTurnOutcome,
    AdapterTurnResult,
    EngineSessionHandle,
    InteractionKind,
    InteractionOption,
    SkillManifest,
)
from ..protocol.contracts import LiveRuntimeEmitter
from ...services.platform.process_supervisor import process_supervisor
from ...services.platform.process_termination import terminate_asyncio_process_tree
from ..auth_detection.signal import extract_auth_signal, is_high_confidence_auth_signal
from .common.prompt_builder_common import render_global_first_attempt_prefix
from .contracts import (
    AdapterExecutionArtifacts,
    AdapterExecutionContext,
    AttemptRunFolderValidator,
    CommandBuilder,
    ConfigComposer,
    PromptBuilder,
    SessionHandleCodec,
    StreamParser,
)
from .types import EngineRunResult, ProcessExecutionResult, RuntimeAuthSignal, RuntimeStreamParseResult

logger = logging.getLogger(__name__)

RUNTIME_DEPENDENCIES_INJECTION_FAILED = "RUNTIME_DEPENDENCIES_INJECTION_FAILED"
_RUNTIME_DEPENDENCY_WARNING_MAX_CHARS = 512


AUTH_DETECTION_MONITOR_INTERVAL_SECONDS = 0.1
AUTH_DETECTION_PROBE_THROTTLE_SECONDS = 0.25


@dataclass
class EngineExecutionAdapter:
    """
    Unified execution adapter compiled from standard components.
    """

    config_composer: ConfigComposer | None = None
    run_folder_validator: AttemptRunFolderValidator | None = None
    prompt_builder: PromptBuilder | None = None
    command_builder: CommandBuilder | None = None
    stream_parser: StreamParser | None = None
    session_codec: SessionHandleCodec | None = None
    process_prefix: str = "Engine"

    async def run(
        self,
        skill: SkillManifest,
        input_data: dict[str, Any],
        run_dir: Path,
        options: dict[str, Any],
        live_runtime_emitter: LiveRuntimeEmitter | None = None,
    ) -> EngineRunResult:
        if (
            self.config_composer is None
            or self.run_folder_validator is None
            or self.prompt_builder is None
            or self.command_builder is None
            or self.stream_parser is None
            or self.session_codec is None
        ):
            raise RuntimeError("execution adapter components are not initialized")
        bootstrap_ctx = AdapterExecutionContext(
            skill=skill,
            run_dir=run_dir,
            input_data={},
            options=options,
        )
        config_path = self.config_composer.compose(bootstrap_ctx)
        self.run_folder_validator.validate(bootstrap_ctx, config_path)

        render_ctx = AdapterExecutionContext(
            skill=skill,
            run_dir=run_dir,
            input_data=input_data,
            options=options,
        )
        prompt = self._resolve_effective_prompt(render_ctx)
        attempt_number = self._resolve_attempt_number(options)
        self._persist_first_attempt_prompt_audit(
            run_dir=run_dir,
            attempt_number=attempt_number,
            prompt=prompt,
        )

        process_result = await self._execute_process(
            prompt,
            run_dir,
            skill,
            options,
            live_runtime_emitter=live_runtime_emitter,
        )
        exit_code = process_result.exit_code
        stdout = process_result.raw_stdout
        stderr = process_result.raw_stderr

        parsed = self.stream_parser.parse(stdout)
        payload = parsed.get("turn_result") if isinstance(parsed, dict) else None
        if isinstance(payload, dict):
            turn_result = AdapterTurnResult.model_validate(payload)
        else:
            turn_result = self._turn_error(message="failed to parse engine output")
        if turn_result.stderr is None and stderr:
            turn_result = turn_result.model_copy(update={"stderr": stderr})

        repair_level = turn_result.repair_level

        artifacts_dir = run_dir / "artifacts"
        artifacts = list(artifacts_dir.glob("**/*")) if artifacts_dir.exists() else []

        return EngineRunResult(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            artifacts_created=artifacts,
            failure_reason=process_result.failure_reason,
            repair_level=repair_level,
            turn_result=turn_result,
            runtime_warnings=process_result.runtime_warnings,
            auth_signal_snapshot=cast(RuntimeAuthSignal | None, process_result.auth_signal_snapshot),
        )

    def _persist_first_attempt_prompt_audit(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        prompt: str,
    ) -> None:
        if attempt_number != 1:
            return
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        request_input_path = audit_dir / "request_input.json"
        fallback_path = audit_dir / "prompt.1.txt"
        field_name = "rendered_prompt_first_attempt"
        try:
            self._append_request_input_audit_fields(
                request_input_path=request_input_path,
                fields={field_name: prompt},
            )
            return
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "[%s] failed to persist first-attempt prompt into request_input.json; writing fallback",
                self.process_prefix,
                exc_info=True,
            )

        try:
            temp_path = fallback_path.with_name(f"{fallback_path.name}.tmp")
            temp_path.write_text(prompt, encoding="utf-8")
            temp_path.replace(fallback_path)
        except OSError:
            logger.warning(
                "[%s] failed to persist first-attempt prompt fallback file",
                self.process_prefix,
                exc_info=True,
            )

    def _append_request_input_audit_fields(
        self,
        *,
        request_input_path: Path,
        fields: dict[str, Any],
    ) -> None:
        payload = json.loads(request_input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request_input snapshot must be a JSON object")
        payload.update(fields)
        temp_path = request_input_path.with_name(f"{request_input_path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(request_input_path)

    def _persist_first_attempt_spawn_command_audit(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        original_command: list[str],
        effective_command: list[str],
        normalization_applied: bool,
        normalization_reason: str,
    ) -> None:
        if attempt_number != 1:
            return
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        request_input_path = audit_dir / "request_input.json"
        fallback_path = audit_dir / "argv.1.json"
        payload = {
            "spawn_command_original_first_attempt": list(original_command),
            "spawn_command_effective_first_attempt": list(effective_command),
            "spawn_command_normalization_applied_first_attempt": bool(normalization_applied),
            "spawn_command_normalization_reason_first_attempt": normalization_reason,
        }
        try:
            self._append_request_input_audit_fields(
                request_input_path=request_input_path,
                fields=payload,
            )
            return
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "[%s] failed to persist first-attempt spawn command into request_input.json; writing fallback",
                self.process_prefix,
                exc_info=True,
            )

        try:
            temp_path = fallback_path.with_name(f"{fallback_path.name}.tmp")
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_path.replace(fallback_path)
        except OSError:
            logger.warning(
                "[%s] failed to persist first-attempt spawn command fallback file",
                self.process_prefix,
                exc_info=True,
            )

    def _is_windows_runtime(self) -> bool:
        return os.name == "nt"

    def _resolve_cmd_shim_path(self, command: str, *, env: dict[str, str]) -> Path | None:
        candidate = Path(command)
        if candidate.is_absolute():
            return candidate if candidate.exists() else None
        resolved = shutil.which(command, path=env.get("PATH"))
        if resolved:
            return Path(resolved)
        return None

    def _split_windows_cmd_argument_fragment(self, fragment: str) -> list[str]:
        if not fragment.strip():
            return []
        tokens = re.findall(r'"[^"]*"|\S+', fragment)
        parsed: list[str] = []
        for token in tokens:
            item = token.strip()
            if len(item) >= 2 and item[0] == '"' and item[-1] == '"':
                item = item[1:-1]
            if item:
                parsed.append(item)
        return parsed

    def _normalize_windows_npm_cmd_shim(
        self,
        command: list[str],
        *,
        env: dict[str, str],
    ) -> tuple[list[str], bool, str]:
        normalized = [str(token) for token in command]
        if not self._is_windows_runtime():
            return normalized, False, "not_applicable"
        if not normalized:
            return normalized, False, "not_applicable"
        command_head = normalized[0].strip()
        if not command_head.lower().endswith(".cmd"):
            return normalized, False, "not_applicable"

        shim_path = self._resolve_cmd_shim_path(command_head, env=env)
        if shim_path is None:
            return normalized, False, "parse_failed_fallback"

        try:
            shim_text = shim_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning(
                "[%s] failed to read npm cmd shim for normalization: %s",
                self.process_prefix,
                shim_path,
                exc_info=True,
            )
            return normalized, False, "parse_failed_fallback"

        match = re.search(
            r'"%_prog%"\s*(?P<fixed>.*?)"%dp0%\\(?P<entry>[^"]+)"\s*%\*',
            shim_text,
            re.IGNORECASE | re.DOTALL,
        )
        if match is None:
            return normalized, False, "parse_failed_fallback"

        entry_relpath = match.group("entry")
        entry_parts = [part for part in PureWindowsPath(entry_relpath).parts if part not in {"\\", "/"}]
        if not entry_parts:
            return normalized, False, "parse_failed_fallback"
        entry_path = shim_path.parent.joinpath(*entry_parts)

        fixed_args = self._split_windows_cmd_argument_fragment(match.group("fixed"))
        node_path = shim_path.parent / "node.exe"
        node_command = str(node_path) if node_path.exists() else "node"
        rewritten = [node_command, str(entry_path), *fixed_args, *normalized[1:]]
        return rewritten, True, "npm_cmd_shim_rewritten"

    def build_start_command(
        self,
        ctx: AdapterExecutionContext | None = None,
        *,
        prompt: str | None = None,
        options: dict[str, Any] | None = None,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        if self.command_builder is None:
            raise RuntimeError("execution adapter command builder is not initialized")
        if ctx is not None:
            if prompt is None:
                if self.prompt_builder is None:
                    raise RuntimeError("execution adapter prompt builder is not initialized")
                prompt = self._resolve_effective_prompt(ctx)
            if options is None:
                options = ctx.options
        if prompt is None:
            raise RuntimeError("prompt is required to build start command")
        if options is None:
            options = {}
        build = getattr(self.command_builder, "build_start_with_options", None)
        if callable(build):
            return build(
                prompt=prompt,
                options=options,
                passthrough_args=passthrough_args,
                use_profile_defaults=use_profile_defaults,
            )
        legacy_build = getattr(self.command_builder, "build_start", None)
        if callable(legacy_build):
            if ctx is None:
                raise RuntimeError("legacy build_start requires AdapterExecutionContext")
            return legacy_build(ctx, prompt)
        raise RuntimeError("build_start_with_options/build_start is not implemented")

    def build_resume_command(
        self,
        ctx: AdapterExecutionContext | None = None,
        session_handle: EngineSessionHandle | None = None,
        *,
        prompt: str | None = None,
        options: dict[str, Any] | None = None,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        if self.command_builder is None:
            raise RuntimeError("execution adapter command builder is not initialized")
        if session_handle is None:
            raise RuntimeError("session_handle is required to build resume command")
        if ctx is not None:
            if prompt is None:
                if self.prompt_builder is None:
                    raise RuntimeError("execution adapter prompt builder is not initialized")
                prompt = self._resolve_effective_prompt(ctx)
            if options is None:
                options = ctx.options
        if prompt is None:
            raise RuntimeError("prompt is required to build resume command")
        if options is None:
            options = {}
        build = getattr(self.command_builder, "build_resume_with_options", None)
        if callable(build):
            return build(
                prompt=prompt,
                options=options,
                session_handle=session_handle,
                passthrough_args=passthrough_args,
                use_profile_defaults=use_profile_defaults,
            )
        legacy_build = getattr(self.command_builder, "build_resume", None)
        if callable(legacy_build):
            if ctx is None:
                raise RuntimeError("legacy build_resume requires AdapterExecutionContext")
            return legacy_build(ctx, prompt, session_handle)
        raise RuntimeError("build_resume_with_options/build_resume is not implemented")

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        if self.stream_parser is None:
            return {
                "parser": "unknown",
                "confidence": 0.2,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": ["UNKNOWN_ENGINE_PROFILE"],
                "structured_types": [],
            }
        parser = getattr(self.stream_parser, "parse_runtime_stream", None)
        if callable(parser):
            return parser(stdout_raw=stdout_raw, stderr_raw=stderr_raw, pty_raw=pty_raw)
        return {
            "parser": "unknown",
            "confidence": 0.2,
            "session_id": None,
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": ["UNKNOWN_ENGINE_PROFILE"],
            "structured_types": [],
        }

    def extract_session_handle(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        if self.session_codec is None:
            raise RuntimeError("execution adapter session codec is not initialized")
        return self.session_codec.extract(raw_stdout, turn_index)

    def _active_processes(self) -> dict[str, Any]:
        processes = getattr(self, "_active_run_processes", None)
        if not isinstance(processes, dict):
            processes = {}
            setattr(self, "_active_run_processes", processes)
        return processes

    def _set_active_run_process(
        self,
        *,
        run_id: str,
        process: asyncio.subprocess.Process,
        lease_id: str | None,
    ) -> None:
        self._active_processes()[run_id] = {
            "process": process,
            "lease_id": lease_id,
        }

    def _get_active_run_process_entry(self, run_id: str) -> dict[str, Any] | None:
        raw = self._active_processes().get(run_id)
        if isinstance(raw, dict):
            return raw
        if raw is None:
            return None
        return {"process": raw, "lease_id": None}

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return base_env

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: dict[str, Any],
        live_runtime_emitter: LiveRuntimeEmitter | None = None,
    ) -> ProcessExecutionResult:
        runtime_warnings: list[dict[str, str]] = []
        resume_handle = options.get("__resume_session_handle")
        if isinstance(resume_handle, dict):
            command = self.build_resume_command(
                prompt=prompt,
                options=options,
                session_handle=EngineSessionHandle.model_validate(resume_handle),
            )
        else:
            command = self.build_start_command(prompt=prompt, options=options)

        env = self.build_subprocess_env(os.environ.copy())
        original_command = [str(token) for token in command]
        normalized_command, normalization_applied, normalization_reason = self._normalize_windows_npm_cmd_shim(
            original_command,
            env=env,
        )
        runtime_dependencies = self._resolve_runtime_dependencies(skill)
        command_to_execute = list(normalized_command)
        if runtime_dependencies:
            probe_ok, probe_error_summary = await self._probe_uv_dependency_injection(
                run_dir=run_dir,
                env=env,
                dependencies=runtime_dependencies,
                timeout_sec=self._resolve_hard_timeout(options),
            )
            if probe_ok:
                command_to_execute = self._wrap_command_with_uv(
                    command=normalized_command,
                    dependencies=runtime_dependencies,
                )
            else:
                warning_payload = {
                    "code": RUNTIME_DEPENDENCIES_INJECTION_FAILED,
                    "detail": probe_error_summary
                    or "Failed to inject runtime.dependencies with uv; fallback to direct execution.",
                }
                runtime_warnings.append(warning_payload)
                logger.warning(
                    "runtime_dependencies_injection_failed deps=%s detail=%s",
                    ",".join(runtime_dependencies),
                    warning_payload["detail"],
                )

        attempt_number_obj = options.get("__attempt_number")
        attempt_number = (
            attempt_number_obj
            if isinstance(attempt_number_obj, int) and attempt_number_obj > 0
            else 1
        )
        self._persist_first_attempt_spawn_command_audit(
            run_dir=run_dir,
            attempt_number=attempt_number,
            original_command=original_command,
            effective_command=command_to_execute,
            normalization_applied=normalization_applied,
            normalization_reason=normalization_reason,
        )

        proc = await self._create_subprocess(*command_to_execute, cwd=run_dir, env=env)
        process_result = await self._capture_process_output(
            proc,
            run_dir,
            options,
            self.process_prefix,
            live_runtime_emitter=live_runtime_emitter,
        )
        process_result.runtime_warnings.extend(runtime_warnings)
        return process_result

    # Backward-compatible component wrappers used by existing tests and thin callers.
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: dict[str, Any]) -> Path:
        if self.config_composer is None:
            raise RuntimeError("execution adapter config composer is not initialized")
        return self.config_composer.compose(
            AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data={},
                options=options,
            )
        )

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: dict[str, Any],
    ) -> Path:
        if self.run_folder_validator is None:
            raise RuntimeError("execution adapter run-folder validator is not initialized")
        return self.run_folder_validator.validate(
            AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data={},
                options=options,
            ),
            config_path,
        )

    def _resolve_attempt_number(self, options: dict[str, Any] | None) -> int:
        if not isinstance(options, dict):
            return 1
        attempt_number_obj = options.get("__attempt_number")
        if isinstance(attempt_number_obj, int) and attempt_number_obj > 0:
            return attempt_number_obj
        return 1

    def _prepend_global_first_attempt_prefix(
        self,
        *,
        ctx: AdapterExecutionContext,
        prompt: str,
    ) -> str:
        profile = getattr(self, "profile", None)
        if profile is None:
            return prompt
        prefix = render_global_first_attempt_prefix(ctx=ctx, profile=profile)
        if not prefix.strip():
            return prompt
        body = prompt.lstrip("\n")
        prefix_text = prefix.rstrip()
        if not body:
            return prefix_text
        return f"{prefix_text}\n\n{body}"

    def _resolve_effective_prompt(self, ctx: AdapterExecutionContext) -> str:
        if self.prompt_builder is None:
            raise RuntimeError("execution adapter prompt builder is not initialized")
        prompt = self.prompt_builder.render(ctx)
        prompt_override = ctx.options.get("__prompt_override")
        if isinstance(prompt_override, str) and prompt_override.strip():
            prompt = prompt_override
        if self._resolve_attempt_number(ctx.options) != 1:
            return prompt
        return self._prepend_global_first_attempt_prefix(ctx=ctx, prompt=prompt)

    def _build_prompt(
        self,
        skill: SkillManifest,
        run_dir: Path,
        input_data: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> str:
        return self._resolve_effective_prompt(
            AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data=input_data,
                options=options or {},
            )
        )

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        if self.stream_parser is None:
            return self._turn_error(message="stream parser is not initialized")
        parsed = self.stream_parser.parse(raw_stdout)
        payload = parsed.get("turn_result") if isinstance(parsed, dict) else None
        if isinstance(payload, dict):
            return AdapterTurnResult.model_validate(payload)
        return self._turn_error(message="failed to parse engine output")

    def parse_output(self, raw_stdout: str) -> dict[str, Any]:
        if self.stream_parser is None:
            return {"turn_result": self._turn_error(message="stream parser is not initialized").model_dump(mode="json")}
        parsed = self.stream_parser.parse(raw_stdout)
        if isinstance(parsed, dict):
            return parsed
        return {"turn_result": self._turn_error(message="failed to parse engine output").model_dump(mode="json")}

    def bootstrap(self, ctx: AdapterExecutionContext) -> tuple[str, Path]:
        config_path = self._construct_config(ctx.skill, ctx.run_dir, ctx.options)
        workspace_dir = self._setup_environment(ctx.skill, ctx.run_dir, config_path, ctx.options)
        prompt = self._resolve_effective_prompt(ctx) if self.prompt_builder is not None else ""
        return prompt, workspace_dir

    async def _capture_process_output(
        self,
        proc: asyncio.subprocess.Process,
        run_dir: Path,
        options: dict[str, Any],
        prefix: str,
        live_runtime_emitter: LiveRuntimeEmitter | None = None,
    ) -> ProcessExecutionResult:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        auth_engine = self._resolve_auth_detection_engine(options=options)
        auth_idle_grace_sec = self._resolve_auth_detection_idle_grace_seconds()
        auth_signal: RuntimeAuthSignal | None = None
        auth_detection_armed = False
        auth_early_exit = False
        last_output_monotonic = time.monotonic()
        last_probe_monotonic = 0.0
        detection_lock = asyncio.Lock()
        attempt_number_obj = options.get("__attempt_number")
        attempt_number = attempt_number_obj if isinstance(attempt_number_obj, int) and attempt_number_obj > 0 else 1
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        stdout_log_path = audit_dir / f"stdout.{attempt_number}.log"
        stderr_log_path = audit_dir / f"stderr.{attempt_number}.log"
        io_chunks_path = audit_dir / f"io_chunks.{attempt_number}.jsonl"
        stdout_log = stdout_log_path.open("w", encoding="utf-8")
        stderr_log = stderr_log_path.open("w", encoding="utf-8")
        io_chunks_log = io_chunks_path.open("w", encoding="utf-8")
        io_chunks_lock = asyncio.Lock()
        io_chunk_seq = 0
        io_chunks_write_failed = False

        async def _probe_auth_detection(force: bool = False) -> None:
            nonlocal auth_signal, auth_detection_armed, last_probe_monotonic
            if auth_engine is None:
                return
            now = time.monotonic()
            if not force and (now - last_probe_monotonic) < AUTH_DETECTION_PROBE_THROTTLE_SECONDS:
                return
            last_probe_monotonic = now
            if detection_lock.locked():
                return
            async with detection_lock:
                current_stdout = "".join(stdout_chunks)
                current_stderr = "".join(stderr_chunks)
                runtime_parse_result = self._parse_runtime_stream_for_auth_detection(
                    raw_stdout=current_stdout,
                    raw_stderr=current_stderr,
                )
                signal = extract_auth_signal(runtime_parse_result)
                if isinstance(signal, dict):
                    auth_signal = signal
                if is_high_confidence_auth_signal(signal):
                    matched_pattern = (
                        str(signal.get("matched_pattern_id") or "<none>")
                        if isinstance(signal, dict)
                        else "<none>"
                    )
                    if not auth_detection_armed:
                        logger.info(
                            "[%s] auth detection armed engine=%s matched_pattern=%s",
                            prefix,
                            auth_engine,
                            matched_pattern,
                        )
                    auth_detection_armed = True

        async def read_stream(
            stream: asyncio.StreamReader | None,
            chunks: list[str],
            tag: str,
            should_print: bool,
            log_file: Any,
            stream_name: str,
        ) -> None:
            nonlocal last_output_monotonic, io_chunk_seq, io_chunks_write_failed
            if stream is None:
                return
            offset = 0
            while True:
                chunk = await stream.read(1024)
                if not chunk:
                    break
                decoded_chunk = chunk.decode("utf-8", errors="replace")
                chunks.append(decoded_chunk)
                log_file.write(decoded_chunk)
                log_file.flush()
                if not io_chunks_write_failed:
                    try:
                        async with io_chunks_lock:
                            io_chunk_seq += 1
                            io_chunks_log.write(
                                json.dumps(
                                    {
                                        "seq": io_chunk_seq,
                                        "ts": datetime.utcnow().isoformat(),
                                        "stream": stream_name,
                                        "byte_from": offset,
                                        "byte_to": offset + len(chunk),
                                        "payload_b64": base64.b64encode(chunk).decode("ascii"),
                                        "encoding": "base64",
                                    },
                                    ensure_ascii=False,
                                )
                            )
                            io_chunks_log.write("\n")
                            io_chunks_log.flush()
                    except OSError:
                        io_chunks_write_failed = True
                        logger.exception("[%s] failed to append io_chunks journal", prefix)
                last_output_monotonic = time.monotonic()
                if live_runtime_emitter is not None:
                    await live_runtime_emitter.on_stream_chunk(
                        stream=stream_name,
                        text=decoded_chunk,
                        byte_from=offset,
                        byte_to=offset + len(chunk),
                    )
                offset += len(chunk)
                if should_print:
                    logger.info("[%s]%s", tag, decoded_chunk.rstrip())
                await _probe_auth_detection()

        stdout_task = asyncio.create_task(
            read_stream(proc.stdout, stdout_chunks, f"{prefix} OUT ", False, stdout_log, "stdout")
        )
        stderr_task = asyncio.create_task(
            read_stream(proc.stderr, stderr_chunks, f"{prefix} ERR ", False, stderr_log, "stderr")
        )

        run_id_obj = options.get("__run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else None
        lease_id: str | None = None
        if run_id:
            request_id_obj = options.get("__request_id")
            request_id = request_id_obj if isinstance(request_id_obj, str) and request_id_obj else None
            attempt_obj = options.get("__attempt_number")
            attempt_number_value = attempt_obj if isinstance(attempt_obj, int) and attempt_obj > 0 else None
            engine_obj = options.get("__engine_name")
            engine_name = engine_obj if isinstance(engine_obj, str) and engine_obj else None
            lease_id = process_supervisor.register_asyncio_process(
                owner_kind="run_attempt",
                owner_id=f"{run_id}:{attempt_number}",
                process=proc,
                request_id=request_id,
                run_id=run_id,
                attempt_number=attempt_number_value,
                engine=engine_name,
                metadata={"run_dir": str(run_dir)},
            )
            self._set_active_run_process(run_id=run_id, process=proc, lease_id=lease_id)

        timeout_sec = self._resolve_hard_timeout(options)
        timed_out = False
        try:
            if live_runtime_emitter is not None:
                await live_runtime_emitter.on_process_started()
            started_monotonic = time.monotonic()
            while True:
                if proc.returncode is not None:
                    break
                now = time.monotonic()
                if now - started_monotonic >= timeout_sec:
                    timed_out = True
                    logger.error("[%s] hard timeout reached (%ss), terminating process", prefix, timeout_sec)
                    await self._terminate_process_tree(proc, prefix)
                    break
                if (
                    auth_detection_armed
                    and auth_signal is not None
                    and now - last_output_monotonic >= auth_idle_grace_sec
                ):
                    auth_early_exit = True
                    logger.warning(
                        "[%s] auth detection early-exit triggered after %.2fs idle (engine=%s)",
                        prefix,
                        auth_idle_grace_sec,
                        auth_engine,
                    )
                    await self._terminate_process_tree(proc, prefix)
                    break
                await asyncio.sleep(AUTH_DETECTION_MONITOR_INTERVAL_SECONDS)
            await _probe_auth_detection(force=True)
            if proc.returncode is None:
                await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            timed_out = True
            logger.error("[%s] process wait timed out after termination, forcing close", prefix)
            await self._terminate_process_tree(proc, prefix)
        finally:
            try:
                await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task, return_exceptions=True),
                    timeout=5,
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] stream readers did not finish in time; cancelling", prefix)
                stdout_task.cancel()
                stderr_task.cancel()
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            stdout_log.close()
            stderr_log.close()
            io_chunks_log.close()
            if run_id:
                self._active_processes().pop(run_id, None)
            process_supervisor.release(lease_id, reason="run_attempt_finalized")

        raw_stdout = "".join(stdout_chunks)
        raw_stderr = "".join(stderr_chunks)
        returncode = proc.returncode if proc.returncode is not None else 1
        failure_reason: str | None = None
        if auth_early_exit:
            failure_reason = "AUTH_REQUIRED"
        elif is_high_confidence_auth_signal(auth_signal) and returncode != 0:
            failure_reason = "AUTH_REQUIRED"
        elif timed_out:
            failure_reason = "TIMEOUT"
        if live_runtime_emitter is not None:
            await live_runtime_emitter.on_process_exit(
                exit_code=returncode,
                failure_reason=failure_reason,
            )
        return ProcessExecutionResult(
            exit_code=returncode,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            failure_reason=failure_reason,
            auth_signal_snapshot=auth_signal,
        )

    async def cancel_run_process(self, run_id: str) -> bool:
        entry = self._get_active_run_process_entry(run_id)
        if entry is None:
            return False
        proc = entry.get("process")
        lease_id = entry.get("lease_id")
        if isinstance(lease_id, str) and lease_id:
            await process_supervisor.terminate_lease_async(
                lease_id,
                reason=f"{self.__class__.__name__}:cancel_run_process",
            )
            return True
        if not isinstance(proc, asyncio.subprocess.Process):
            return False
        await self._terminate_process_tree(proc, f"{self.__class__.__name__}Cancel")
        return True

    async def _create_subprocess(self, *cmd: str, cwd: Path, env: dict[str, str]) -> asyncio.subprocess.Process:
        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": str(cwd),
            "env": env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        else:
            kwargs["start_new_session"] = True
        return await asyncio.create_subprocess_exec(*cmd, **kwargs)

    def _resolve_runtime_dependencies(self, skill: SkillManifest) -> list[str]:
        runtime = getattr(skill, "runtime", None)
        dependencies_obj = getattr(runtime, "dependencies", None)
        if not isinstance(dependencies_obj, list):
            return []
        normalized: list[str] = []
        for item in dependencies_obj:
            if not isinstance(item, str):
                continue
            dep = item.strip()
            if not dep:
                continue
            normalized.append(dep)
        return normalized

    def _wrap_command_with_uv(self, *, command: list[str], dependencies: list[str]) -> list[str]:
        wrapped: list[str] = ["uv", "run"]
        for dependency in dependencies:
            wrapped.extend(["--with", dependency])
        wrapped.append("--")
        wrapped.extend(command)
        return wrapped

    def _summarize_runtime_dependency_error(self, text: str) -> str:
        compact = " ".join(text.replace("\r", "\n").split())
        if not compact:
            return "uv dependency probe failed with empty output."
        if len(compact) > _RUNTIME_DEPENDENCY_WARNING_MAX_CHARS:
            return compact[: _RUNTIME_DEPENDENCY_WARNING_MAX_CHARS - 3] + "..."
        return compact

    async def _probe_uv_dependency_injection(
        self,
        *,
        run_dir: Path,
        env: dict[str, str],
        dependencies: list[str],
        timeout_sec: int,
    ) -> tuple[bool, str | None]:
        probe_cmd = self._wrap_command_with_uv(
            command=["python", "-c", "print('skill-runner-deps-probe')"],
            dependencies=dependencies,
        )
        try:
            probe_proc = await self._create_subprocess(*probe_cmd, cwd=run_dir, env=env)
        except (FileNotFoundError, OSError) as exc:
            return False, self._summarize_runtime_dependency_error(f"failed to spawn uv probe: {exc}")

        probe_timeout = max(1, min(timeout_sec, 120))
        try:
            stdout_raw, stderr_raw = await asyncio.wait_for(probe_proc.communicate(), timeout=probe_timeout)
        except asyncio.TimeoutError:
            await self._terminate_process_tree(probe_proc, f"{self.__class__.__name__}DepsProbe")
            return False, self._summarize_runtime_dependency_error(
                f"uv dependency probe timed out after {probe_timeout}s"
            )

        if probe_proc.returncode == 0:
            return True, None

        stdout_text = stdout_raw.decode("utf-8", errors="replace") if isinstance(stdout_raw, (bytes, bytearray)) else ""
        stderr_text = stderr_raw.decode("utf-8", errors="replace") if isinstance(stderr_raw, (bytes, bytearray)) else ""
        summary = self._summarize_runtime_dependency_error(
            f"uv dependency probe exited {probe_proc.returncode}: {stderr_text or stdout_text}"
        )
        return False, summary

    async def _terminate_process_tree(self, proc: asyncio.subprocess.Process, prefix: str) -> None:
        result = await terminate_asyncio_process_tree(proc)
        if result.outcome == "failed":
            logger.warning("[%s] process termination failed (%s)", prefix, result.detail)

    def _resolve_hard_timeout(self, options: dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError, OverflowError):
            logger.debug(
                "[%s] invalid hard_timeout_seconds=%r; using default=%s",
                self.__class__.__name__,
                candidate,
                default_timeout,
            )
        return default_timeout

    def _resolve_auth_detection_idle_grace_seconds(self) -> float:
        raw = getattr(config.SYSTEM, "AUTH_DETECTION_IDLE_GRACE_SECONDS", 3)
        try:
            parsed = float(raw)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError, OverflowError):
            pass
        return 3.0

    def _resolve_auth_detection_engine(self, options: dict[str, Any]) -> str | None:
        engine_obj = options.get("__engine_name")
        if not isinstance(engine_obj, str):
            return None
        engine = engine_obj.strip().lower()
        return engine if engine else None

    def _parse_runtime_stream_for_auth_detection(
        self,
        *,
        raw_stdout: str,
        raw_stderr: str,
    ) -> dict[str, Any] | None:
        parser = getattr(self, "parse_runtime_stream", None)
        if not callable(parser):
            return None
        try:
            parsed = parser(
                stdout_raw=raw_stdout.encode("utf-8", errors="replace"),
                stderr_raw=raw_stderr.encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
        except (OSError, RuntimeError, TypeError, ValueError, LookupError):
            logger.debug(
                "[%s] parse_runtime_stream failed during auth detection probe",
                self.__class__.__name__,
                exc_info=True,
            )
            return None
        return parsed if isinstance(parsed, dict) else None

    def _resolve_execution_mode(self, options: dict[str, Any]) -> str:
        mode_raw = options.get("execution_mode", "auto")
        if isinstance(mode_raw, str):
            mode = mode_raw.strip().lower()
            if mode in {"auto", "interactive"}:
                return mode
        return "auto"

    def _parse_json_with_deterministic_repair(self, text: str) -> tuple[dict[str, Any] | None, str]:
        parsed = self._try_parse_json_object(text)
        if parsed is not None:
            return parsed, "none"

        stripped = text.strip()
        if stripped and stripped != text:
            parsed = self._try_parse_json_object(stripped)
            if parsed is not None:
                return parsed, "deterministic_generic"

        for candidate in self._extract_code_fence_candidates(text):
            parsed = self._try_parse_json_object(candidate)
            if parsed is not None:
                return parsed, "deterministic_generic"

        first_obj = self._extract_first_json_object(text)
        if first_obj:
            parsed = self._try_parse_json_object(first_obj)
            if parsed is not None:
                return parsed, "deterministic_generic"

        if stripped and stripped != text:
            first_obj = self._extract_first_json_object(stripped)
            if first_obj:
                parsed = self._try_parse_json_object(first_obj)
                if parsed is not None:
                    return parsed, "deterministic_generic"

        return None, "none"

    def _try_parse_json_object(self, text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            return None
        return None

    def _extract_code_fence_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        patterns = [r"```json\s*(\{.*?\})\s*```", r"```(?:json)?\s*(\{.*?\})\s*```"]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                value = match.group(1).strip()
                if value:
                    candidates.append(value)
        return candidates

    def _extract_first_json_object(self, text: str) -> str | None:
        start = -1
        depth = 0
        in_string = False
        escape = False
        for idx, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == "}":
                if depth == 0:
                    continue
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start : idx + 1]
        return None

    def _normalize_interaction_kind(self, raw_kind: Any) -> InteractionKind:
        kind_name = str(raw_kind or "").strip().lower()
        alias_map = {
            "decision": InteractionKind.CHOOSE_ONE.value,
            "confirmation": InteractionKind.CONFIRM.value,
            "clarification": InteractionKind.OPEN_TEXT.value,
        }
        kind_name = alias_map.get(kind_name, kind_name)
        allowed = {
            InteractionKind.CHOOSE_ONE.value,
            InteractionKind.CONFIRM.value,
            InteractionKind.FILL_FIELDS.value,
            InteractionKind.OPEN_TEXT.value,
            InteractionKind.RISK_ACK.value,
        }
        if kind_name not in allowed:
            kind_name = InteractionKind.OPEN_TEXT.value
        return InteractionKind(kind_name)

    def _turn_error(
        self,
        *,
        message: str,
        repair_level: str = "none",
        failure_reason: str | None = None,
    ) -> AdapterTurnResult:
        return AdapterTurnResult(
            outcome=AdapterTurnOutcome.ERROR,
            failure_reason=failure_reason or "ADAPTER_TURN_ERROR",
            repair_level=repair_level,
            final_data={"code": "ADAPTER_TURN_ERROR", "message": message},
        )

    def _normalize_interaction_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[AdapterTurnInteraction | None, str | None]:
        interaction_id_raw = payload.get("interaction_id")
        if interaction_id_raw is None:
            return None, "missing interaction_id"
        try:
            interaction_id = int(interaction_id_raw)
        except (TypeError, ValueError, OverflowError):
            return None, "missing interaction_id"
        if interaction_id <= 0:
            return None, "invalid interaction_id"

        prompt = payload.get("prompt") or payload.get("question")
        if not isinstance(prompt, str) or not prompt.strip():
            return None, "missing prompt"
        kind = self._normalize_interaction_kind(payload.get("kind", InteractionKind.OPEN_TEXT.value))

        options_payload = payload.get("options", [])
        options: list[InteractionOption] = []
        if isinstance(options_payload, list):
            for item in options_payload:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                options.append(InteractionOption(label=label.strip(), value=item.get("value")))

        ui_hints_raw = payload.get("ui_hints")
        ui_hints: dict[str, Any] = {}
        if isinstance(ui_hints_raw, dict):
            ui_hints = dict(ui_hints_raw)

        default_decision_policy_raw = payload.get("default_decision_policy")
        default_decision_policy = (
            default_decision_policy_raw.strip()
            if isinstance(default_decision_policy_raw, str) and default_decision_policy_raw.strip()
            else "engine_judgement"
        )

        required_fields_raw = payload.get("required_fields")
        required_fields: list[str] = []
        if isinstance(required_fields_raw, list):
            required_fields = [
                field.strip()
                for field in required_fields_raw
                if isinstance(field, str) and field.strip()
            ]

        context = payload.get("context")
        if context is not None and not isinstance(context, dict):
            context = None

        interaction = AdapterTurnInteraction(
            interaction_id=interaction_id,
            kind=kind,
            prompt=prompt.strip(),
            options=options,
            ui_hints=ui_hints,
            default_decision_policy=default_decision_policy,
            required_fields=required_fields,
            context=context,
        )
        return interaction, None

    def _extract_interaction_from_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[AdapterTurnInteraction | None, str | None]:
        interaction_payload: dict[str, Any] | None = None
        if isinstance(payload.get("interaction"), dict):
            interaction_payload = payload["interaction"]
        elif isinstance(payload.get("ask_user"), dict):
            interaction_payload = payload["ask_user"]
        if interaction_payload is None:
            return None, "missing interaction payload"
        return self._normalize_interaction_payload(interaction_payload)

    def _build_turn_result_from_payload(self, payload: dict[str, Any], repair_level: str) -> AdapterTurnResult:
        outcome_raw = payload.get("outcome")
        outcome_name = outcome_raw.strip().lower() if isinstance(outcome_raw, str) else ""
        if outcome_name == AdapterTurnOutcome.FINAL.value:
            final_payload = payload.get("final_data")
            if isinstance(final_payload, dict):
                return AdapterTurnResult(
                    outcome=AdapterTurnOutcome.FINAL,
                    final_data=final_payload,
                    repair_level=repair_level,
                )
            return self._turn_error(message="invalid final_data payload", repair_level=repair_level)

        if outcome_name == AdapterTurnOutcome.ASK_USER.value:
            interaction, reason = self._extract_interaction_from_payload(payload)
            if interaction is None:
                return self._turn_error(
                    message=f"invalid ask_user payload: {reason}",
                    repair_level=repair_level,
                )
            return AdapterTurnResult(
                outcome=AdapterTurnOutcome.ASK_USER,
                interaction=interaction,
                repair_level=repair_level,
            )

        if outcome_name == AdapterTurnOutcome.ERROR.value:
            failure_reason = payload.get("failure_reason")
            message = payload.get("message")
            if (not isinstance(message, str) or not message.strip()) and isinstance(payload.get("error"), dict):
                nested = payload["error"].get("message")
                if isinstance(nested, str):
                    message = nested
            if not isinstance(message, str) or not message.strip():
                message = "engine returned error outcome"
            return self._turn_error(
                message=message,
                repair_level=repair_level,
                failure_reason=failure_reason if isinstance(failure_reason, str) else None,
            )

        is_legacy_ask_user = (
            isinstance(payload.get("ask_user"), dict)
            or (payload.get("action") == AdapterTurnOutcome.ASK_USER.value and isinstance(payload.get("interaction"), dict))
            or (payload.get("type") == AdapterTurnOutcome.ASK_USER.value and isinstance(payload.get("interaction"), dict))
        )
        if is_legacy_ask_user:
            interaction, reason = self._extract_interaction_from_payload(payload)
            if interaction is None:
                return self._turn_error(
                    message=f"invalid ask_user payload: {reason}",
                    repair_level=repair_level,
                )
            return AdapterTurnResult(
                outcome=AdapterTurnOutcome.ASK_USER,
                interaction=interaction,
                repair_level=repair_level,
            )

        return AdapterTurnResult(
            outcome=AdapterTurnOutcome.FINAL,
            final_data=payload,
            repair_level=repair_level,
        )

    def _materialize_output_payload(self, turn_result: AdapterTurnResult) -> dict[str, Any]:
        if turn_result.outcome == AdapterTurnOutcome.FINAL:
            return turn_result.final_data or {}
        if turn_result.outcome == AdapterTurnOutcome.ASK_USER and turn_result.interaction is not None:
            interaction_payload = turn_result.interaction.model_dump(mode="json")
            return {
                "outcome": AdapterTurnOutcome.ASK_USER.value,
                "action": AdapterTurnOutcome.ASK_USER.value,
                "ask_user": interaction_payload,
                "interaction": interaction_payload,
            }
        return {"outcome": AdapterTurnOutcome.ERROR.value, "error": turn_result.final_data or {}}

    def as_artifacts(
        self,
        *,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        repair_level: str = "none",
        failure_reason: str | None = None,
        structured_payload: dict[str, Any] | None = None,
        session_handle: EngineSessionHandle | None = None,
    ) -> AdapterExecutionArtifacts:
        return AdapterExecutionArtifacts(
            exit_code=exit_code,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            repair_level=repair_level,
            failure_reason=failure_reason,
            session_handle=session_handle,
            structured_payload=structured_payload,
        )
