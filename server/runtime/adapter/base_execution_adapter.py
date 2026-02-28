from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from .contracts import (
    AdapterExecutionArtifacts,
    AdapterExecutionContext,
    CommandBuilder,
    ConfigComposer,
    PromptBuilder,
    SessionHandleCodec,
    StreamParser,
    WorkspaceProvisioner,
)
from .types import EngineRunResult, ProcessExecutionResult, RuntimeStreamParseResult

logger = logging.getLogger(__name__)


AUTH_REQUIRED_PATTERNS = (
    re.compile(r"enter authorization code", re.IGNORECASE),
    re.compile(r"visit this url", re.IGNORECASE),
    re.compile(r"401\\s+unauthorized", re.IGNORECASE),
    re.compile(r"missing\\s+bearer", re.IGNORECASE),
    re.compile(r"server_oauth2_required", re.IGNORECASE),
    re.compile(r"需要使用服务器oauth2流程", re.IGNORECASE),
)


@dataclass
class EngineExecutionAdapter:
    """
    Unified execution adapter compiled from standard components.
    """

    config_composer: ConfigComposer | None = None
    workspace_provisioner: WorkspaceProvisioner | None = None
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
    ) -> EngineRunResult:
        is_interactive_reply_turn = "__interactive_reply_payload" in options
        if (
            self.config_composer is None
            or self.workspace_provisioner is None
            or self.prompt_builder is None
            or self.command_builder is None
            or self.stream_parser is None
            or self.session_codec is None
        ):
            raise RuntimeError("execution adapter components are not initialized")
        if not is_interactive_reply_turn:
            bootstrap_ctx = AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data={},
                options=options,
            )
            config_path = self.config_composer.compose(bootstrap_ctx)
            self.workspace_provisioner.prepare(bootstrap_ctx, config_path)

        render_ctx = AdapterExecutionContext(
            skill=skill,
            run_dir=run_dir,
            input_data=input_data,
            options=options,
        )
        prompt = self.prompt_builder.render(render_ctx)
        prompt_override = options.get("__prompt_override")
        if isinstance(prompt_override, str) and prompt_override.strip():
            prompt = prompt_override

        process_result = await self._execute_process(prompt, run_dir, skill, options)
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

        result_payload = self._materialize_output_payload(turn_result)
        repair_level = turn_result.repair_level

        artifacts_dir = run_dir / "artifacts"
        artifacts = list(artifacts_dir.glob("**/*")) if artifacts_dir.exists() else []

        result_path = run_dir / "result" / "result.json"
        if result_payload is not None:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, indent=2, ensure_ascii=False)

        return EngineRunResult(
            exit_code=exit_code,
            raw_stdout=stdout,
            raw_stderr=stderr,
            output_file_path=result_path if result_path.exists() else None,
            artifacts_created=artifacts,
            failure_reason=process_result.failure_reason,
            repair_level=repair_level,
            turn_result=turn_result,
        )

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
                prompt = self.prompt_builder.render(ctx)
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
                prompt = self.prompt_builder.render(ctx)
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

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return base_env

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: dict[str, Any],
    ) -> ProcessExecutionResult:
        _ = skill
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
        proc = await self._create_subprocess(*command, cwd=run_dir, env=env)
        return await self._capture_process_output(proc, run_dir, options, self.process_prefix)

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
        if self.workspace_provisioner is None:
            raise RuntimeError("execution adapter workspace provisioner is not initialized")
        return self.workspace_provisioner.prepare(
            AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data={},
                options=options,
            ),
            config_path,
        )

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: dict[str, Any]) -> str:
        if self.prompt_builder is None:
            raise RuntimeError("execution adapter prompt builder is not initialized")
        return self.prompt_builder.render(
            AdapterExecutionContext(
                skill=skill,
                run_dir=run_dir,
                input_data=input_data,
                options={},
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
        prompt = self.prompt_builder.render(ctx) if self.prompt_builder is not None else ""
        return prompt, workspace_dir

    async def _capture_process_output(
        self,
        proc: asyncio.subprocess.Process,
        run_dir: Path,
        options: dict[str, Any],
        prefix: str,
    ) -> ProcessExecutionResult:
        verbose_opt = options.get("verbose", 0)
        if isinstance(verbose_opt, bool):
            verbose_level = 1 if verbose_opt else 0
        else:
            verbose_level = int(verbose_opt)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def read_stream(
            stream: asyncio.StreamReader | None,
            chunks: list[str],
            tag: str,
            should_print: bool,
        ) -> None:
            if stream is None:
                return
            while True:
                chunk = await stream.read(1024)
                if not chunk:
                    break
                decoded_chunk = chunk.decode("utf-8", errors="replace")
                chunks.append(decoded_chunk)
                if should_print:
                    logger.info("[%s]%s", tag, decoded_chunk.rstrip())

        stdout_task = asyncio.create_task(
            read_stream(proc.stdout, stdout_chunks, f"{prefix} OUT ", verbose_level >= 1)
        )
        stderr_task = asyncio.create_task(
            read_stream(proc.stderr, stderr_chunks, f"{prefix} ERR ", verbose_level >= 2)
        )

        run_id_obj = options.get("__run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else None
        if run_id:
            self._active_processes()[run_id] = proc

        timeout_sec = self._resolve_hard_timeout(options)
        timed_out = False
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            timed_out = True
            logger.error("[%s] hard timeout reached (%ss), terminating process", prefix, timeout_sec)
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
            if run_id:
                self._active_processes().pop(run_id, None)

        raw_stdout = "".join(stdout_chunks)
        raw_stderr = "".join(stderr_chunks)
        returncode = proc.returncode if proc.returncode is not None else 1
        failure_reason: str | None = None
        if self._looks_like_auth_required(raw_stdout, raw_stderr) and (timed_out or returncode != 0):
            failure_reason = "AUTH_REQUIRED"
        elif timed_out:
            failure_reason = "TIMEOUT"
        return ProcessExecutionResult(
            exit_code=returncode,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            failure_reason=failure_reason,
        )

    async def cancel_run_process(self, run_id: str) -> bool:
        proc = self._active_processes().get(run_id)
        if proc is None:
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

    async def _terminate_process_tree(self, proc: asyncio.subprocess.Process, prefix: str) -> None:
        if proc.returncode is not None:
            return
        if os.name == "nt":
            await self._terminate_process_tree_windows(proc, prefix)
            return
        await self._terminate_process_tree_posix(proc, prefix)

    async def _terminate_process_tree_posix(self, proc: asyncio.subprocess.Process, prefix: str) -> None:
        try:
            pgid = os.getpgid(proc.pid)
        except Exception:
            pgid = None

        if pgid is not None and pgid == proc.pid:
            try:
                os.killpg(pgid, signal.SIGTERM)
                await asyncio.wait_for(proc.wait(), timeout=5)
                return
            except asyncio.TimeoutError:
                logger.warning("[%s] process group SIGTERM timeout, escalating to SIGKILL", prefix)
                try:
                    os.killpg(pgid, signal.SIGKILL)
                    await asyncio.wait_for(proc.wait(), timeout=5)
                    return
                except Exception:
                    pass
            except ProcessLookupError:
                return
            except Exception:
                logger.warning("[%s] process group termination failed", prefix, exc_info=True)
        elif pgid is not None:
            logger.warning(
                "[%s] subprocess is not process-group leader (pgid=%s,pid=%s); fallback terminate",
                prefix,
                pgid,
                proc.pid,
            )

        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=3)
            except Exception:
                logger.warning("[%s] fallback terminate/kill failed", prefix, exc_info=True)

    async def _terminate_process_tree_windows(self, proc: asyncio.subprocess.Process, prefix: str) -> None:
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            try:
                proc.send_signal(ctrl_break)
                await asyncio.wait_for(proc.wait(), timeout=3)
                return
            except Exception:
                pass

        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)
            return
        except Exception:
            pass

        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:
            logger.warning("[%s] windows terminate/kill failed", prefix, exc_info=True)

    def _resolve_hard_timeout(self, options: dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return default_timeout

    def _looks_like_auth_required(self, stdout: str, stderr: str) -> bool:
        combined = f"{stdout}\n{stderr}"
        return any(pattern.search(combined) for pattern in AUTH_REQUIRED_PATTERNS)

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
        except Exception:
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
        except Exception:
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
