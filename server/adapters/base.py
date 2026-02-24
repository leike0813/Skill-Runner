from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, TypedDict, NotRequired
import asyncio
import json
import re
import logging
import os
import signal
import subprocess
from pathlib import Path
from ..models import (
    AdapterTurnInteraction,
    AdapterTurnOutcome,
    AdapterTurnResult,
    EngineSessionHandle,
    InteractionKind,
    InteractionOption,
    SkillManifest,
)
from ..config import config


AUTH_REQUIRED_PATTERNS = (
    re.compile(r"enter authorization code", re.IGNORECASE),
    re.compile(r"visit this url", re.IGNORECASE),
    re.compile(r"401\\s+unauthorized", re.IGNORECASE),
    re.compile(r"missing\\s+bearer", re.IGNORECASE),
    re.compile(r"server_oauth2_required", re.IGNORECASE),
    re.compile(r"需要使用服务器oauth2流程", re.IGNORECASE),
)


class ProcessExecutionResult:
    """Normalized process execution result from adapter subprocess."""

    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        failure_reason: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.failure_reason = failure_reason


class RuntimeStreamRawRow(TypedDict):
    stream: str
    line: str
    byte_from: int
    byte_to: int


class RuntimeStreamRawRef(TypedDict):
    stream: str
    byte_from: int
    byte_to: int


class RuntimeAssistantMessage(TypedDict):
    text: str
    raw_ref: NotRequired[RuntimeStreamRawRef | None]


class RuntimeStreamParseResult(TypedDict):
    parser: str
    confidence: float
    session_id: Optional[str]
    assistant_messages: List[RuntimeAssistantMessage]
    raw_rows: List[RuntimeStreamRawRow]
    diagnostics: List[str]
    structured_types: List[str]


class EngineRunResult:
    """
    Standardized payload returned by an EngineAdapter execution.
    Contains raw outputs, file paths, and artifact metadata.
    """
    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        output_file_path: Optional[Path] = None,
        artifacts_created: Optional[List[Path]] = None,
        failure_reason: Optional[str] = None,
        repair_level: str = "none",
        turn_result: Optional[AdapterTurnResult] = None,
    ):
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.output_file_path = output_file_path
        self.artifacts_created = artifacts_created or []
        self.failure_reason = failure_reason
        self.repair_level = repair_level
        self.turn_result = turn_result

logger = logging.getLogger(__name__)


class EngineAdapter(ABC):
    """
    Abstract Base Class for Execution Adapters (e.g. Gemini, Codex).
    
    Defines the standard 5-phase execution lifecycle:
    1. Configuration
    2. Environment Setup
    3. Context & Prompt
    4. Execution
    5. Result Parsing
    """
    
    async def run(
        self,
        skill: SkillManifest,
        input_data: Dict[str, Any],
        run_dir: Path,
        options: Dict[str, Any]
    ) -> EngineRunResult:
        """
        Orchestrates the standard execution lifecycle.
        Subclasses should implement the phases, not override this method unless absolutely necessary.
        """
        is_interactive_reply_turn = "__interactive_reply_payload" in options
        if not is_interactive_reply_turn:
            # 1. Configuration
            config_path = self._construct_config(skill, run_dir, options)
            # 2. Environment Setup
            self._setup_environment(skill, run_dir, config_path, options)
        
        # 3. Context & Prompt
        prompt = self._build_prompt(skill, run_dir, input_data)
        prompt_override = options.get("__prompt_override")
        if isinstance(prompt_override, str) and prompt_override.strip():
            prompt = prompt_override
        
        # 4. Execution
        # We assume command construction + execution happens here
        process_result = await self._execute_process(prompt, run_dir, skill, options)
        exit_code = process_result.exit_code
        stdout = process_result.raw_stdout
        stderr = process_result.raw_stderr
        
        # 5. Result Parsing
        turn_result = self._parse_output(stdout)
        if turn_result.stderr is None and stderr:
            turn_result = turn_result.model_copy(update={"stderr": stderr})
        result_payload = self._materialize_output_payload(turn_result)
        repair_level = turn_result.repair_level
        
        # 5.1 Artifact Scanning (Standardized here or in subclass? Standard here is better)
        artifacts_dir = run_dir / "artifacts"
        artifacts = list(artifacts_dir.glob("**/*")) if artifacts_dir.exists() else []
        
        # 5.2 Write Result Json if parsed
        result_path = run_dir / "result" / "result.json"
        if result_payload is not None:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                json.dump(result_payload, f, indent=2)
                
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

    def _active_processes(self) -> Dict[str, Any]:
        processes = getattr(self, "_active_run_processes", None)
        if not isinstance(processes, dict):
            processes = {}
            setattr(self, "_active_run_processes", processes)
        return processes

    async def _capture_process_output(
        self,
        proc,
        run_dir: Path,
        options: Dict[str, Any],
        prefix: str,
    ) -> ProcessExecutionResult:
        """Read subprocess stdout/stderr streams, log them, and return outputs."""
        verbose_opt = options.get("verbose", 0)
        if isinstance(verbose_opt, bool):
            verbose_level = 1 if verbose_opt else 0
        else:
            verbose_level = int(verbose_opt)

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def read_stream(stream, chunks, tag, should_print):
            while True:
                chunk = await stream.read(1024)
                if not chunk:
                    break
                decoded_chunk = chunk.decode("utf-8", errors="replace")
                chunks.append(decoded_chunk)
                if should_print:
                    logger.info("[%s]%s", tag, decoded_chunk.rstrip())

        stdout_task = asyncio.create_task(
            read_stream(
                proc.stdout,
                stdout_chunks,
                f"{prefix} OUT ",
                verbose_level >= 1,
            )
        )
        stderr_task = asyncio.create_task(
            read_stream(
                proc.stderr,
                stderr_chunks,
                f"{prefix} ERR ",
                verbose_level >= 2,
            )
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
        failure_reason: Optional[str] = None
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

    async def _create_subprocess(
        self,
        *cmd: str,
        cwd: Path,
        env: Dict[str, str],
    ):
        kwargs: Dict[str, Any] = {
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

    async def _terminate_process_tree(self, proc, prefix: str) -> None:
        if proc.returncode is not None:
            return
        if os.name == "nt":
            await self._terminate_process_tree_windows(proc, prefix)
            return
        await self._terminate_process_tree_posix(proc, prefix)

    async def _terminate_process_tree_posix(self, proc, prefix: str) -> None:
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
                logger.warning("[%s] process group termination failed, fallback to terminate/kill", prefix, exc_info=True)
        elif pgid is not None:
            logger.warning(
                "[%s] subprocess is not process-group leader (pgid=%s,pid=%s); fallback to direct terminate",
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

    async def _terminate_process_tree_windows(self, proc, prefix: str) -> None:
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

    def _resolve_hard_timeout(self, options: Dict[str, Any]) -> int:
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

    def _parse_json_with_deterministic_repair(self, text: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Deterministic generic repair:
        - strict parse
        - trim
        - code fence extraction
        - first JSON object extraction
        """
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

    def _try_parse_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    def _extract_code_fence_candidates(self, text: str) -> List[str]:
        candidates: List[str] = []
        patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```(?:json)?\s*(\{.*?\})\s*```",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                value = match.group(1).strip()
                if value:
                    candidates.append(value)
        return candidates

    def _extract_first_json_object(self, text: str) -> Optional[str]:
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
                    return text[start:idx + 1]
        return None

    def _resolve_execution_mode(self, options: Dict[str, Any]) -> str:
        mode_raw = options.get("execution_mode", "auto")
        if isinstance(mode_raw, str):
            mode = mode_raw.strip().lower()
            if mode in {"auto", "interactive"}:
                return mode
        return "auto"

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
        failure_reason: Optional[str] = None,
    ) -> AdapterTurnResult:
        return AdapterTurnResult(
            outcome=AdapterTurnOutcome.ERROR,
            failure_reason=failure_reason or "ADAPTER_TURN_ERROR",
            repair_level=repair_level,
            final_data={
                "code": "ADAPTER_TURN_ERROR",
                "message": message,
            },
        )

    def _normalize_interaction_payload(
        self,
        payload: Dict[str, Any],
    ) -> Tuple[Optional[AdapterTurnInteraction], Optional[str]]:
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
        payload: Dict[str, Any],
    ) -> Tuple[Optional[AdapterTurnInteraction], Optional[str]]:
        interaction_payload: Optional[Dict[str, Any]] = None
        if isinstance(payload.get("interaction"), dict):
            interaction_payload = payload["interaction"]
        elif isinstance(payload.get("ask_user"), dict):
            interaction_payload = payload["ask_user"]
        if interaction_payload is None:
            return None, "missing interaction payload"
        return self._normalize_interaction_payload(interaction_payload)

    def _build_turn_result_from_payload(
        self,
        payload: Dict[str, Any],
        repair_level: str,
    ) -> AdapterTurnResult:
        outcome_raw = payload.get("outcome")
        if isinstance(outcome_raw, str):
            outcome_name = outcome_raw.strip().lower()
        else:
            outcome_name = ""

        if outcome_name == AdapterTurnOutcome.FINAL.value:
            final_payload = payload.get("final_data")
            if isinstance(final_payload, dict):
                return AdapterTurnResult(
                    outcome=AdapterTurnOutcome.FINAL,
                    final_data=final_payload,
                    repair_level=repair_level,
                )
            return self._turn_error(
                message="invalid final_data payload",
                repair_level=repair_level,
            )

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
            if not isinstance(message, str) or not message.strip():
                error_payload = payload.get("error")
                if isinstance(error_payload, dict):
                    nested_message = error_payload.get("message")
                    if isinstance(nested_message, str):
                        message = nested_message
            if not isinstance(message, str) or not message.strip():
                message = "engine returned error outcome"
            return self._turn_error(
                message=message,
                repair_level=repair_level,
                failure_reason=failure_reason if isinstance(failure_reason, str) else None,
            )

        is_legacy_ask_user = (
            isinstance(payload.get("ask_user"), dict)
            or (
                payload.get("action") == AdapterTurnOutcome.ASK_USER.value
                and isinstance(payload.get("interaction"), dict)
            )
            or (
                payload.get("type") == AdapterTurnOutcome.ASK_USER.value
                and isinstance(payload.get("interaction"), dict)
            )
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

        # Backward compatible: plain dict payload is treated as final data.
        return AdapterTurnResult(
            outcome=AdapterTurnOutcome.FINAL,
            final_data=payload,
            repair_level=repair_level,
        )

    def _materialize_output_payload(self, turn_result: AdapterTurnResult) -> Dict[str, Any]:
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
        error_payload = turn_result.final_data or {}
        return {
            "outcome": AdapterTurnOutcome.ERROR.value,
            "error": error_payload,
        }

    def extract_session_handle(
        self,
        raw_stdout: str,
        turn_index: int,
    ) -> EngineSessionHandle:
        raise RuntimeError(f"{self.__class__.__name__} does not implement session extraction")

    def build_resume_command(
        self,
        prompt: str,
        options: Dict[str, Any],
        session_handle: EngineSessionHandle,
        passthrough_args: Optional[List[str]] = None,
        use_profile_defaults: bool = True,
    ) -> List[str]:
        raise RuntimeError(f"{self.__class__.__name__} does not implement resume command")

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: Optional[List[str]] = None,
        use_profile_defaults: bool = True,
    ) -> List[str]:
        raise RuntimeError(f"{self.__class__.__name__} does not implement start command")

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        return {
            "parser": "unknown",
            "confidence": 0.2,
            "session_id": None,
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": ["UNKNOWN_ENGINE_PROFILE"],
            "structured_types": [],
        }

    @abstractmethod
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        """Phase 1: Generate engine-specific configuration file in workspace."""
        pass

    @abstractmethod
    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        """Phase 2: Install skill to workspace and patch SKILL.md."""
        pass

    @abstractmethod
    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: Dict[str, Any]) -> str:
        """Phase 3: Resolve inputs and render invocation prompt."""
        pass

    @abstractmethod
    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        """Phase 4: Execute subprocess."""
        pass

    @abstractmethod
    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        """Phase 5: Extract structured result from raw output."""
        pass
