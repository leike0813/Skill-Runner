from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.models import (
    EngineInteractiveProfile,
    ExecutionMode,
    InteractiveErrorCode,
    OrchestratorEventType,
    RunStatus,
    SkillManifest,
)
from server.runtime.session.statechart import timeout_requires_auto_decision
from server.services.platform.schema_validator import schema_validator
from server.services.skill.skill_registry import skill_registry

logger = logging.getLogger(__name__)


class RunCanceled(Exception):
    """Raised when run is canceled by user request."""


@dataclass
class RunJobRequest:
    run_id: str
    skill_id: str
    engine_name: str
    options: Dict[str, Any]
    cache_key: Optional[str] = None
    skill_override: Optional[SkillManifest] = None
    temp_request_id: Optional[str] = None


@dataclass
class RunJobRuntimeState:
    request_id: Optional[str] = None
    execution_mode: str = ExecutionMode.AUTO.value
    is_interactive: bool = False
    interactive_auto_reply: bool = False
    interactive_profile: Optional[EngineInteractiveProfile] = None
    attempt_number: int = 1
    attempt_started_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RunJobOutcome:
    run_id: str
    final_status: Optional[RunStatus] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class _RunJobLifecyclePipeline:
    async def run_job(
        self: Any,
        run_id: str,
        skill_id: str,
        engine_name: str,
        options: Dict[str, Any],
        cache_key: Optional[str] = None,
        skill_override: Optional[SkillManifest] = None,
        temp_request_id: Optional[str] = None,
    ) -> RunJobOutcome:
        """
        Background task to execute the skill.

        Args:
            run_id: Unique UUID of the run.
            skill_id: ID of the skill to execute.
            engine_name: 'codex' or 'gemini'.
            options: Execution options (e.g. runtime model config and policies).

        Side Effects:
            - Updates 'status.json' in run_dir.
            - Writes '.audit/stdout.{attempt}.log', '.audit/stderr.{attempt}.log'.
            - Writes 'result/result.json'.
        """
        slot_acquired = False
        release_slot_on_exit = True
        run_dir: Path | None = None
        run_store = self._run_store_backend()
        workspace_manager = self._workspace_backend()
        concurrency_manager = self._concurrency_backend()
        run_folder_trust_manager = self._trust_manager_backend()
        await concurrency_manager.acquire_slot()
        slot_acquired = True
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            logger.error("Run dir %s not found", run_id)
            return RunJobOutcome(run_id=run_id)
        request_record = await run_store.get_request_by_run_id(run_id)
        request_id = request_record.get("request_id") if request_record else None
        execution_mode = str(
            options.get(
                "execution_mode",
                (request_record or {}).get("runtime_options", {}).get(
                    "execution_mode", ExecutionMode.AUTO.value
                ),
            )
        )
        is_interactive = execution_mode == ExecutionMode.INTERACTIVE.value
        interactive_auto_reply = self._resolve_interactive_auto_reply(
            options=options,
            request_record=request_record or {},
        )
        interactive_profile: Optional[EngineInteractiveProfile] = None
        if is_interactive and request_id:
            interactive_profile = await self._resolve_interactive_profile(
                request_id=request_id,
                engine_name=engine_name,
                options=options,
            )
        attempt_number = await self._resolve_attempt_number(
            request_id=request_id,
            is_interactive=is_interactive,
        )
        attempt_started_at = datetime.utcnow()
        fs_before_snapshot = self._capture_filesystem_snapshot(run_dir)
        process_exit_code: Optional[int] = None
        process_failure_reason: Optional[str] = None
        process_raw_stdout = ""
        process_raw_stderr = ""
        turn_payload_for_completion: Dict[str, Any] = {}
        done_signal_found_in_payload = False
        if await run_store.is_cancel_requested(run_id):
            canceled_error = self._build_canceled_error()
            result_path = self._write_canceled_result(run_dir, canceled_error)
            self._update_status(
                run_dir,
                RunStatus.CANCELED,
                error=canceled_error,
                effective_session_timeout_sec=(
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                ),
            )
            await run_store.update_run_status(
                run_id,
                RunStatus.CANCELED,
                str(result_path) if result_path is not None else None,
            )
            if temp_request_id:
                with contextlib.suppress(OSError, RuntimeError, TypeError, ValueError):
                    from server.services.skill.temp_skill_run_store import temp_skill_run_store

                    await temp_skill_run_store.update_status(
                        temp_request_id,
                        RunStatus.CANCELED,
                        error=canceled_error["message"],
                    )
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()
            return RunJobOutcome(
                run_id=run_id,
                final_status=RunStatus.CANCELED,
                error_code=str(canceled_error.get("code")),
                error_message=str(canceled_error.get("message")),
            )
        final_status: Optional[RunStatus] = None
        normalized_error_message: Optional[str] = None
        final_validation_warnings: list[str] = []
        final_error_code: Optional[str] = None
        trust_registered = False
        adapter: Any | None = None

        # 1. Update status to RUNNING
        self._update_status(
            run_dir,
            RunStatus.RUNNING,
            effective_session_timeout_sec=(
                interactive_profile.session_timeout_sec if interactive_profile is not None else None
            ),
        )
        self._append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="lifecycle",
            type_name=OrchestratorEventType.LIFECYCLE_RUN_STARTED.value,
            data={"status": RunStatus.RUNNING.value},
        )
        self._update_latest_run_id(run_id)

        try:
            # 2. Get Skill
            skill = skill_override or skill_registry.get_skill(skill_id)
            if (
                skill is None
                and is_interactive
                and "__interactive_reply_payload" in options
            ):
                skill = self._load_skill_from_run_dir(
                    run_dir=run_dir,
                    skill_id=skill_id,
                    engine_name=engine_name,
                )
            if not skill:
                raise ValueError(f"Skill {skill_id} not found during execution")
            if not skill.schemas or not all(key in skill.schemas for key in ("input", "parameter", "output")):
                raise ValueError("Schema missing: input/parameter/output must be defined")

            # 3. Get Adapter
            adapter = self.adapters.get(engine_name)
            if not adapter:
                raise ValueError(f"Engine {engine_name} not supported")

            # 4. Load Input
            with open(run_dir / "input.json", "r") as input_file:
                input_data = json.load(input_file)

            # 4.1 Validate Input & Parameters
            real_params = input_data.get("parameter", {})
            input_errors = []

            # 1. Validate 'parameter' (Values)
            if skill.schemas and "parameter" in skill.schemas:
                # Validator expects the data to match the schema
                # strict validation of the parameter payload
                input_errors.extend(schema_validator.validate_schema(skill, real_params, "parameter"))

            # 2. Validate mixed 'input' (file + inline)
            if skill.schemas and "input" in skill.schemas:
                input_errors.extend(
                    schema_validator.validate_input_for_execution(skill, run_dir, input_data)
                )

            if input_errors:
                raise ValueError(f"Input validation failed: {str(input_errors)}")

            if await run_store.is_cancel_requested(run_id):
                raise RunCanceled()

            run_folder_trust_manager.register_run_folder(engine_name, run_dir)
            trust_registered = True
            run_options = dict(options)
            run_options["__run_id"] = run_id
            run_options["__attempt_number"] = attempt_number
            if is_interactive and request_id and interactive_profile:
                await self._inject_interactive_resume_context(
                    request_id=request_id,
                    profile=interactive_profile,
                    options=run_options,
                    run_dir=run_dir,
                )

            # 5. Execute
            try:
                result = await adapter.run(skill, input_data, run_dir, run_options)
            finally:
                if trust_registered:
                    try:
                        run_folder_trust_manager.remove_run_folder(engine_name, run_dir)
                    except (OSError, RuntimeError, ValueError):
                        # Best-effort cleanup: trust-entry removal must not mask run result.
                        logger.warning(
                            "Failed to cleanup run folder trust for engine=%s run_id=%s",
                            engine_name,
                            run_id,
                            exc_info=True,
                        )
                    trust_registered = False
            process_exit_code = result.exit_code
            process_failure_reason = result.failure_reason
            process_raw_stdout = result.raw_stdout or ""
            process_raw_stderr = result.raw_stderr or ""
            if await run_store.is_cancel_requested(run_id):
                raise RunCanceled()

            # 6. Verify Result and Normalize
            warnings: list[str] = []
            output_data: Dict[str, Any] = {}
            schema_output_errors: list[str] = []
            terminal_validation_errors: list[str] = []
            pending_interaction: Optional[Dict[str, Any]] = None
            pending_interaction_candidate: Optional[Dict[str, Any]] = None
            repair_level = result.repair_level or "none"
            has_structured_output = False
            done_marker_found_in_stream = self._contains_done_marker_in_stream(
                adapter=adapter,
                raw_stdout=result.raw_stdout,
                raw_stderr=result.raw_stderr,
            )
            done_signal_found = done_marker_found_in_stream
            if result.exit_code == 0:
                if result.output_file_path and result.output_file_path.exists():
                    try:
                        with open(result.output_file_path, "r") as f:
                            raw_output_data = json.load(f)
                        if isinstance(raw_output_data, dict):
                            has_structured_output = True
                            turn_payload_for_completion = dict(raw_output_data)
                            output_data, done_signal_found_in_payload = (
                                self._strip_done_marker_for_output_validation(raw_output_data)
                            )
                            done_signal_found = (
                                done_signal_found_in_payload or done_marker_found_in_stream
                            )
                        else:
                            schema_output_errors = ["Output JSON must be an object"]
                            output_data = {}
                        if not schema_output_errors:
                            schema_output_errors = schema_validator.validate_output(skill, output_data)
                        if not schema_output_errors and repair_level == "deterministic_generic":
                            warnings.append("OUTPUT_REPAIRED_GENERIC")
                    except (json.JSONDecodeError, OSError, TypeError, ValueError) as e:
                        # Boundary guard: adapter output may be malformed or unreadable.
                        schema_output_errors = [f"Failed to validate output schema: {str(e)}"]
                        output_data = {}
                else:
                    schema_output_errors = ["Output JSON missing or unreadable"]

            if is_interactive and not done_signal_found:
                pending_interaction_candidate = self._extract_pending_interaction(
                    output_data,
                    fallback_interaction_id=attempt_number,
                )
                stream_pending_interaction = self._extract_pending_interaction_from_stream(
                    adapter=adapter,
                    raw_stdout=result.raw_stdout,
                    raw_stderr=result.raw_stderr,
                    fallback_interaction_id=attempt_number,
                )
                if stream_pending_interaction is not None:
                    if pending_interaction_candidate is None:
                        pending_interaction_candidate = stream_pending_interaction
                if pending_interaction_candidate is None:
                    pending_interaction_candidate = self._infer_pending_interaction(
                        output_data,
                        fallback_interaction_id=attempt_number,
                    )
                if pending_interaction_candidate is None:
                    pending_interaction_candidate = self._infer_pending_interaction_from_runtime_stream(
                        adapter=adapter,
                        raw_stdout=result.raw_stdout,
                        raw_stderr=result.raw_stderr,
                        fallback_interaction_id=attempt_number,
                    )

            # 6.1 Normalization (N0)
            # Create standard envelope
            artifacts_dir = run_dir / "artifacts"
            artifacts = []
            if artifacts_dir.exists():
                for path in artifacts_dir.rglob("*"):
                    if path.is_file():
                        artifacts.append(path.relative_to(run_dir).as_posix())
            artifacts.sort()
            required_artifacts = [
                artifact.pattern
                for artifact in skill.artifacts
                if artifact.required
            ] if skill.artifacts else []
            missing_artifacts = []
            for pattern in required_artifacts:
                expected_path = f"artifacts/{pattern}"
                if expected_path not in artifacts:
                    missing_artifacts.append(pattern)
            artifact_errors: list[str] = []
            if missing_artifacts:
                artifact_errors.append(
                    f"Missing required artifacts: {', '.join(missing_artifacts)}"
                )
            forced_failure_reason = result.failure_reason if result.failure_reason in {
                "AUTH_REQUIRED",
                "TIMEOUT",
                InteractiveErrorCode.SESSION_RESUME_FAILED.value,
            } else None

            normalized_status = "success"
            if forced_failure_reason or result.exit_code != 0:
                normalized_status = "failed"
            elif is_interactive:
                soft_completion = (
                    (not done_signal_found)
                    and has_structured_output
                    and not schema_output_errors
                )
                if done_signal_found:
                    terminal_validation_errors = [*schema_output_errors, *artifact_errors]
                    if terminal_validation_errors:
                        normalized_status = "failed"
                elif soft_completion:
                    terminal_validation_errors = [*artifact_errors]
                    if terminal_validation_errors:
                        normalized_status = "failed"
                    else:
                        warnings.append("INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER")
                else:
                    max_attempt = skill.max_attempt
                    if max_attempt is not None and attempt_number >= max_attempt:
                        forced_failure_reason = (
                            InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value
                        )
                        normalized_status = "failed"
                    else:
                        normalized_status = RunStatus.WAITING_USER.value
                        pending_interaction = pending_interaction_candidate
            else:
                terminal_validation_errors = [*schema_output_errors, *artifact_errors]
                if terminal_validation_errors:
                    normalized_status = "failed"

            if (
                normalized_status == RunStatus.WAITING_USER.value
                and pending_interaction is not None
                and is_interactive
                and request_id
                and interactive_profile
            ):
                raw_runtime_output = "\n".join(
                    part for part in [result.raw_stdout, result.raw_stderr] if isinstance(part, str)
                )
                wait_status = await self._persist_waiting_interaction(
                    adapter=adapter,
                    run_id=run_id,
                    run_dir=run_dir,
                    request_id=request_id,
                    profile=interactive_profile,
                    interactive_auto_reply=interactive_auto_reply,
                    pending_interaction=pending_interaction,
                    raw_runtime_output=raw_runtime_output,
                )
                if wait_status is not None:
                    forced_failure_reason = wait_status
                    normalized_status = "failed"
                    pending_interaction = None

            has_output_error = bool(terminal_validation_errors)
            normalized_error: dict[str, Any] | None = None
            if normalized_status == RunStatus.WAITING_USER.value:
                normalized_error = None
            elif normalized_status != "success":
                error_code: Optional[str] = None
                if forced_failure_reason == "AUTH_REQUIRED":
                    error_code = "AUTH_REQUIRED"
                    error_message = "AUTH_REQUIRED: engine authentication is required or expired"
                elif forced_failure_reason == "TIMEOUT":
                    error_code = "TIMEOUT"
                    effective_timeout = self._resolve_hard_timeout_seconds(options)
                    error_message = (
                        f"TIMEOUT: engine execution exceeded hard timeout "
                        f"({effective_timeout}s)"
                    )
                elif forced_failure_reason in {
                    InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                    InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value,
                }:
                    error_code = forced_failure_reason
                    error_message = str(forced_failure_reason)
                elif has_output_error:
                    error_message = "; ".join(terminal_validation_errors)
                else:
                    error_message = f"Exit code {result.exit_code}"
                normalized_error = {
                    "code": error_code,
                    "message": error_message,
                    "stderr": result.raw_stderr,
                }
            normalized_result = {
                "status": normalized_status,
                "data": output_data if normalized_status == "success" else None,
                "artifacts": artifacts,
                "repair_level": repair_level,
                "validation_warnings": warnings,
                "error": normalized_error,
                "pending_interaction": pending_interaction,
            }
            final_validation_warnings = list(warnings)
            final_error_code = (
                str(normalized_error.get("code"))
                if isinstance(normalized_error, dict) and normalized_error.get("code")
                else None
            )

            # Allow adapter to communicate error via output if present
            if result.exit_code != 0 and result.raw_stderr:
                pass  # already handled in error

            # Overwrite result.json with normalized version
            # Ensure parent dir exists (it should)
            result_path = run_dir / "result" / "result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                json.dump(normalized_result, f, indent=2)

            # 7. Finalize status and bundles
            if normalized_status == "success":
                final_status = RunStatus.SUCCEEDED
            elif normalized_status == RunStatus.WAITING_USER.value:
                final_status = RunStatus.WAITING_USER
            else:
                final_status = RunStatus.FAILED
            normalized_error_message = normalized_error["message"] if normalized_error else None
            if (
                final_status == RunStatus.WAITING_USER
                and interactive_profile is not None
                and request_id
                and pending_interaction
            ):
                if timeout_requires_auto_decision(interactive_auto_reply):
                    delay_sec = max(1, int(interactive_profile.session_timeout_sec))
                    asyncio.create_task(
                        self._auto_decide_after_timeout(
                            request_id=request_id,
                            run_id=run_id,
                            delay_sec=delay_sec,
                        )
                    )
            if final_status != RunStatus.WAITING_USER:
                self._build_run_bundle(run_dir, debug=False)
                self._build_run_bundle(run_dir, debug=True)
            self._update_status(
                run_dir,
                final_status,
                error=normalized_error,
                warnings=warnings,
                effective_session_timeout_sec=(
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                ),
            )
            await run_store.update_run_status(run_id, final_status, str(result_path))
            if final_status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}:
                self._append_orchestrator_event(
                    run_dir=run_dir,
                    attempt_number=attempt_number,
                    category="lifecycle",
                    type_name=OrchestratorEventType.LIFECYCLE_RUN_TERMINAL.value,
                    data={"status": final_status.value},
                )
            if cache_key and final_status == RunStatus.SUCCEEDED:
                if temp_request_id:
                    await run_store.record_temp_cache_entry(cache_key, run_id)
                else:
                    await run_store.record_cache_entry(cache_key, run_id)

        except RunCanceled:
            final_status = RunStatus.CANCELED
            canceled_error = self._build_canceled_error()
            normalized_error_message = canceled_error["message"]
            final_error_code = str(canceled_error.get("code"))
            final_validation_warnings = []
            result_path = self._write_canceled_result(run_dir, canceled_error) if run_dir else None
            if run_dir:
                self._update_status(
                    run_dir,
                    RunStatus.CANCELED,
                    error=canceled_error,
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                )
            await run_store.update_run_status(
                run_id,
                RunStatus.CANCELED,
                str(result_path) if result_path is not None else None,
            )
            if run_dir:
                self._append_orchestrator_event(
                    run_dir=run_dir,
                    attempt_number=attempt_number,
                    category="lifecycle",
                    type_name=OrchestratorEventType.LIFECYCLE_RUN_CANCELED.value,
                    data={"status": RunStatus.CANCELED.value},
                )
        except (RuntimeError, OSError, TypeError, ValueError, LookupError) as e:
            # Orchestration boundary: normalize unknown runtime exceptions into terminal error payload.
            logger.exception("Job failed")
            final_status = RunStatus.FAILED
            normalized_error = self._error_from_exception(e)
            normalized_error_message = str(normalized_error.get("message", str(e)))
            final_error_code = (
                str(normalized_error.get("code"))
                if isinstance(normalized_error, dict) and normalized_error.get("code")
                else None
            )
            final_validation_warnings = []
            if run_dir:
                self._update_status(
                    run_dir,
                    RunStatus.FAILED,
                    error=normalized_error,
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                )
            await run_store.update_run_status(run_id, RunStatus.FAILED)
            if run_dir:
                self._append_orchestrator_event(
                    run_dir=run_dir,
                    attempt_number=attempt_number,
                    category="error",
                    type_name=OrchestratorEventType.ERROR_RUN_FAILED.value,
                    data={"message": normalized_error_message or "unknown"},
                )
        finally:
            if run_dir is not None:
                try:
                    self._write_attempt_audit_artifacts(
                        run_dir=run_dir,
                        run_id=run_id,
                        request_id=request_id,
                        engine_name=engine_name,
                        execution_mode=execution_mode,
                        attempt_number=attempt_number,
                        started_at=attempt_started_at,
                        finished_at=datetime.utcnow(),
                        status=final_status,
                        fs_before_snapshot=fs_before_snapshot,
                        process_exit_code=process_exit_code,
                        process_failure_reason=process_failure_reason,
                        process_raw_stdout=process_raw_stdout,
                        process_raw_stderr=process_raw_stderr,
                        adapter=adapter,
                        turn_payload=turn_payload_for_completion,
                        validation_warnings=final_validation_warnings,
                        terminal_error_code=final_error_code,
                        options=options,
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    # Observability side-effect only: do not alter terminal run status.
                    logger.warning(
                        "Failed to write attempt audit artifacts for run_id=%s attempt=%s",
                        run_id,
                        attempt_number,
                        exc_info=True,
                    )
            if trust_registered and run_dir:
                try:
                    run_folder_trust_manager.remove_run_folder(engine_name, run_dir)
                except (OSError, RuntimeError, ValueError):
                    # Best-effort cleanup during finalization.
                    logger.warning(
                        "Failed to cleanup run folder trust in finalizer for engine=%s run_id=%s",
                        engine_name,
                        run_id,
                        exc_info=True,
                    )
            if temp_request_id and final_status in {
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
                RunStatus.CANCELED,
            }:
                try:
                    from server.services.skill.temp_skill_run_manager import temp_skill_run_manager

                    temp_skill_run_manager.on_terminal(
                        temp_request_id,
                        final_status,
                        error=normalized_error_message,
                        debug_keep_temp=bool(options.get("debug_keep_temp")),
                    )
                except (RuntimeError, OSError, TypeError, ValueError):
                    # Temp lifecycle callback must not change parent run terminal status.
                    logger.warning(
                        "Failed to finalize temporary-skill lifecycle for request %s",
                        temp_request_id,
                        exc_info=True,
                    )
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()

        return RunJobOutcome(
            run_id=run_id,
            final_status=final_status,
            error_code=final_error_code,
            error_message=normalized_error_message,
            warnings=list(final_validation_warnings),
        )


class RunJobLifecycleService:
    async def run(
        self,
        *,
        orchestrator: Any,
        request: RunJobRequest,
    ) -> RunJobOutcome:
        return await _RunJobLifecyclePipeline.run_job(
            orchestrator,
            run_id=request.run_id,
            skill_id=request.skill_id,
            engine_name=request.engine_name,
            options=request.options,
            cache_key=request.cache_key,
            skill_override=request.skill_override,
            temp_request_id=request.temp_request_id,
        )
