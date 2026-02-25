import asyncio
import contextlib
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml  # type: ignore[import-untyped]
from ..models import (
    EngineSessionHandle,
    EngineInteractiveProfile,
    ExecutionMode,
    InteractiveResolutionMode,
    InteractiveErrorCode,
    OrchestratorEventType,
    RunStatus,
    SkillManifest,
)
from ..services.agent_cli_manager import AgentCliManager
from ..services.workspace_manager import workspace_manager
from ..services.skill_registry import skill_registry
from ..services.engine_adapter_registry import engine_adapter_registry
from ..services.schema_validator import schema_validator
from ..services.run_store import run_store
from ..services.concurrency_manager import concurrency_manager
from ..services.run_folder_trust_manager import run_folder_trust_manager
from ..services.session_timeout import resolve_session_timeout
from ..services.engine_policy import apply_engine_policy_to_manifest
from ..services.manifest_artifact_inference import infer_manifest_artifacts
from ..services.session_statechart import (
    SessionEvent,
    timeout_requires_auto_decision,
    waiting_recovery_event,
    waiting_reply_target_status,
)
from .protocol_factories import (
    make_diagnostic_warning_payload,
    make_orchestrator_event,
    make_resume_command,
)
from .protocol_schema_registry import (
    ProtocolSchemaViolation,
    validate_orchestrator_event,
    validate_pending_interaction,
    validate_resume_command,
)
from ..config import config

DONE_MARKER_STREAM_PATTERN = re.compile(
    r'(?:\\)?"__SKILL_DONE__(?:\\)?"\s*:\s*true',
    re.IGNORECASE,
)


class RunCanceled(Exception):
    """Raised when run is canceled by user request."""


class JobOrchestrator:
    """
    Manages the background execution of skills.
    
    Responsibilities:
    - Coordinates lifecycle of a run (QUEUED -> RUNNING -> SUCCEEDED/FAILED).
    - Resolves the correct EngineAdapter based on the request.
    - Validates inputs before execution.
    - Captures results and normalizes outputs.
    - Writes status updates to the workspace.
    """
    def __init__(self):
        self.agent_cli_manager = AgentCliManager()
        self.adapters = engine_adapter_registry.adapter_map()

    async def run_job(
        self,
        run_id: str,
        skill_id: str,
        engine_name: str,
        options: Dict[str, Any],
        cache_key: Optional[str] = None,
        skill_override: Optional[SkillManifest] = None,
        temp_request_id: Optional[str] = None,
    ):
        """
        Background task to execute the skill.
        
        Args:
            run_id: Unique UUID of the run.
            skill_id: ID of the skill to execute.
            engine_name: 'codex' or 'gemini'.
            options: Execution options (e.g. verbose flag, model config).
            
        Side Effects:
            - Updates 'status.json' in run_dir.
            - Writes '.audit/stdout.{attempt}.log', '.audit/stderr.{attempt}.log'.
            - Writes 'result/result.json'.
        """
        slot_acquired = False
        release_slot_on_exit = True
        run_dir: Path | None = None
        await concurrency_manager.acquire_slot()
        slot_acquired = True
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            logger.error("Run dir %s not found", run_id)
            return
        request_record = run_store.get_request_by_run_id(run_id)
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
        interactive_require_user_reply = self._resolve_interactive_require_user_reply(
            options=options,
            request_record=request_record or {},
        )
        interactive_profile: Optional[EngineInteractiveProfile] = None
        if is_interactive and request_id:
            interactive_profile = self._resolve_interactive_profile(
                request_id=request_id,
                engine_name=engine_name,
                options=options,
            )
        attempt_number = self._resolve_attempt_number(
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
        if run_store.is_cancel_requested(run_id):
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
            run_store.update_run_status(
                run_id,
                RunStatus.CANCELED,
                str(result_path) if result_path is not None else None,
            )
            if temp_request_id:
                with contextlib.suppress(Exception):
                    from .temp_skill_run_store import temp_skill_run_store

                    temp_skill_run_store.update_status(
                        temp_request_id,
                        RunStatus.CANCELED,
                        error=canceled_error["message"],
                    )
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()
            return
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
            with open(run_dir / "input.json", 'r') as input_file:
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

            if run_store.is_cancel_requested(run_id):
                raise RunCanceled()

            run_folder_trust_manager.register_run_folder(engine_name, run_dir)
            trust_registered = True
            run_options = dict(options)
            run_options["__run_id"] = run_id
            run_options["__attempt_number"] = attempt_number
            if is_interactive and request_id and interactive_profile:
                self._inject_interactive_resume_context(
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
                    except Exception:
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
            if run_store.is_cancel_requested(run_id):
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
                    except Exception as e:
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
                wait_status = self._persist_waiting_interaction(
                    adapter=adapter,
                    run_id=run_id,
                    run_dir=run_dir,
                    request_id=request_id,
                    profile=interactive_profile,
                    interactive_require_user_reply=interactive_require_user_reply,
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
                    error_message = forced_failure_reason
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
                 pass # already handled in error
                 
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
                if timeout_requires_auto_decision(interactive_require_user_reply):
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
            run_store.update_run_status(run_id, final_status, str(result_path))
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
                    run_store.record_temp_cache_entry(cache_key, run_id)
                else:
                    run_store.record_cache_entry(cache_key, run_id)

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
            run_store.update_run_status(
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
        except Exception as e:
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
            run_store.update_run_status(run_id, RunStatus.FAILED)
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
                except Exception:
                    logger.warning(
                        "Failed to write attempt audit artifacts for run_id=%s attempt=%s",
                        run_id,
                        attempt_number,
                        exc_info=True,
                    )
            if trust_registered and run_dir:
                try:
                    run_folder_trust_manager.remove_run_folder(engine_name, run_dir)
                except Exception:
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
                    from .temp_skill_run_manager import temp_skill_run_manager
                    temp_skill_run_manager.on_terminal(
                        temp_request_id,
                        final_status,
                        error=normalized_error_message,
                        debug_keep_temp=bool(options.get("debug_keep_temp")),
                    )
                except Exception:
                    logger.warning(
                        "Failed to finalize temporary-skill lifecycle for request %s",
                        temp_request_id,
                        exc_info=True,
                    )
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()

    async def cancel_run(
        self,
        *,
        run_id: str,
        engine_name: str,
        run_dir: Path,
        status: RunStatus,
        request_id: Optional[str] = None,
        temp_request_id: Optional[str] = None,
    ) -> bool:
        changed = run_store.set_cancel_requested(run_id, True)
        if status == RunStatus.RUNNING:
            adapter = self.adapters.get(engine_name)
            if adapter is not None:
                with contextlib.suppress(Exception):
                    await adapter.cancel_run_process(run_id)

        canceled_error = self._build_canceled_error()
        self._write_canceled_result(run_dir, canceled_error)
        self._update_status(
            run_dir,
            RunStatus.CANCELED,
            error=canceled_error,
            effective_session_timeout_sec=(
                run_store.get_effective_session_timeout(request_id) if request_id else None
            ),
        )
        run_store.update_run_status(run_id, RunStatus.CANCELED)

        if temp_request_id:
            from .temp_skill_run_store import temp_skill_run_store

            temp_skill_run_store.update_status(
                temp_request_id,
                RunStatus.CANCELED,
                error=canceled_error["message"],
            )
        return changed

    def _build_canceled_error(self) -> Dict[str, Any]:
        return {
            "code": "CANCELED_BY_USER",
            "message": "Canceled by user request",
        }

    def _write_canceled_result(self, run_dir: Optional[Path], error: Dict[str, Any]) -> Optional[Path]:
        if run_dir is None:
            return None
        result_payload: Dict[str, Any] = {
            "status": RunStatus.CANCELED.value,
            "data": None,
            "artifacts": [],
            "repair_level": "none",
            "validation_warnings": [],
            "error": error,
            "pending_interaction": None,
        }
        result_path = run_dir / "result" / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result_path

    def _update_status(
        self,
        run_dir: Path,
        status: RunStatus,
        error: Optional[Dict] = None,
        warnings: Optional[List[str]] = None,
        effective_session_timeout_sec: Optional[int] = None,
    ):
        # In v0, we might just rely on checking result/ but let's write a status file
        # This mirrors what WorkspaceManager does but updates it
        # Ideally WorkspaceManager should own this writing logic
        # For simplicity, I'll write a simple status.json sidecar
        
        warnings_list = warnings or []
        status_data = {
            "status": status,
            "updated_at": str(datetime.now()),
            "error": error,
            "warnings": warnings_list,
            "effective_session_timeout_sec": effective_session_timeout_sec,
        }
        with open(run_dir / "status.json", "w") as f:
            json.dump(status_data, f)

    def _update_latest_run_id(self, run_id: str):
        """Updates the latest_run_id file in the runs directory."""
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        try:
            with open(runs_dir / "latest_run_id", "w") as f:
                f.write(run_id)
        except Exception as e:
            logger.exception("Failed to update latest_run_id")

    def _load_skill_from_run_dir(
        self,
        *,
        run_dir: Path,
        skill_id: str,
        engine_name: str,
    ) -> Optional[SkillManifest]:
        workspace_prefix = {
            "codex": ".codex",
            "gemini": ".gemini",
            "iflow": ".iflow",
            "opencode": ".opencode",
        }.get(engine_name, f".{engine_name}")
        skill_dir = run_dir / workspace_prefix / "skills" / skill_id
        runner_path = skill_dir / "assets" / "runner.json"
        if not runner_path.exists() or not runner_path.is_file():
            return None
        try:
            data = json.loads(runner_path.read_text(encoding="utf-8"))
            data = infer_manifest_artifacts(data, skill_dir)
            apply_engine_policy_to_manifest(data)
            return SkillManifest(**data, path=skill_dir)
        except Exception:
            logger.warning(
                "Failed to load skill manifest from run directory for resume: run_id=%s skill_id=%s",
                run_dir.name,
                skill_id,
                exc_info=True,
            )
            return None

    def _build_run_bundle(self, run_dir: Path, debug: bool) -> str:
        bundle_dir = run_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_filename = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        bundle_path = bundle_dir / bundle_filename
        manifest_filename = "manifest_debug.json" if debug else "manifest.json"
        manifest_path = bundle_dir / manifest_filename

        entries = []
        bundle_candidates = self._bundle_candidates(run_dir, debug, bundle_path, manifest_path)
        for path in bundle_candidates:
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            entries.append({
                "path": rel_path,
                "size": path.stat().st_size,
                "sha256": self._hash_file(path)
            })

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"files": entries}, f, indent=2)

        if bundle_path.exists():
            bundle_path.unlink()

        import zipfile
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in bundle_candidates:
                if not path.is_file():
                    continue
                rel_path = path.relative_to(run_dir).as_posix()
                zf.write(path, rel_path)
            zf.write(manifest_path, manifest_path.relative_to(run_dir).as_posix())

        return bundle_path.relative_to(run_dir).as_posix()

    def _bundle_candidates(self, run_dir: Path, debug: bool, bundle_path: Path, manifest_path: Path) -> list[Path]:
        if debug:
            candidates = [path for path in run_dir.rglob("*") if path.is_file()]
        else:
            candidates = []
            result_path = run_dir / "result" / "result.json"
            if result_path.exists():
                candidates.append(result_path)
            artifacts_dir = run_dir / "artifacts"
            if artifacts_dir.exists():
                candidates.extend([path for path in artifacts_dir.rglob("*") if path.is_file()])

        bundle_dir = run_dir / "bundle"
        candidates = [
            path for path in candidates
            if path != bundle_path and path != manifest_path and path.parent != bundle_dir
        ]
        return candidates

    def _hash_file(self, path: Path) -> str:
        import hashlib

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _resolve_hard_timeout_seconds(self, options: Dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return default_timeout

    def _resolve_attempt_number(self, *, request_id: Optional[str], is_interactive: bool) -> int:
        if not request_id or not is_interactive:
            return 1
        interaction_count = run_store.get_interaction_count(request_id)
        return max(1, int(interaction_count) + 1)

    def _capture_filesystem_snapshot(self, run_dir: Path) -> Dict[str, Dict[str, Any]]:
        snapshot: Dict[str, Dict[str, Any]] = {}
        ignored_prefixes = (
            ".audit/",
            "interactions/",
            ".codex/",
            ".gemini/",
            ".iflow/",
            ".opencode/",
        )
        ignored_files = {
            "opencode.json",
        }
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            if rel_path.startswith(ignored_prefixes):
                continue
            if rel_path in ignored_files:
                continue
            snapshot[rel_path] = {
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "sha256": self._hash_file(path),
            }
        return snapshot

    def _diff_filesystem_snapshot(
        self,
        before_snapshot: Dict[str, Dict[str, Any]],
        after_snapshot: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        before_keys = set(before_snapshot.keys())
        after_keys = set(after_snapshot.keys())
        created = sorted(after_keys - before_keys)
        deleted = sorted(before_keys - after_keys)
        modified = sorted(
            path
            for path in (before_keys & after_keys)
            if before_snapshot[path].get("sha256") != after_snapshot[path].get("sha256")
        )
        return {"created": created, "modified": modified, "deleted": deleted}

    def _find_done_markers(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
        turn_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        done_signal_found = "__SKILL_DONE__" in turn_payload and turn_payload.get("__SKILL_DONE__") is True
        markers: List[Dict[str, Any]] = []
        if adapter is not None:
            try:
                parsed = adapter.parse_runtime_stream(
                    stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                    stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                    pty_raw=b"",
                )
            except Exception:
                parsed = None
                logger.warning("failed to parse runtime stream for done-marker scan", exc_info=True)

            assistant_messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
            if isinstance(assistant_messages, list):
                for item in assistant_messages:
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if not isinstance(text_obj, str) or not text_obj:
                        continue
                    raw_ref_obj = item.get("raw_ref")
                    raw_ref = raw_ref_obj if isinstance(raw_ref_obj, dict) else {}
                    marker_stream_obj = raw_ref.get("stream")
                    marker_stream = (
                        marker_stream_obj
                        if isinstance(marker_stream_obj, str) and marker_stream_obj
                        else "assistant"
                    )
                    marker_byte_from = raw_ref.get("byte_from")
                    marker_byte_to = raw_ref.get("byte_to")
                    for _match in DONE_MARKER_STREAM_PATTERN.finditer(text_obj):
                        markers.append(
                            {
                                "stream": marker_stream,
                                "byte_from": marker_byte_from,
                                "byte_to": marker_byte_to,
                            }
                        )
        return {
            "done_signal_found": done_signal_found,
            "done_marker_found": bool(markers),
            "done_marker_count": len(markers),
            "first_marker": markers[0] if markers else None,
        }

    def _contains_done_marker_in_stream(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
    ) -> bool:
        done_info = self._find_done_markers(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            turn_payload={},
        )
        return bool(done_info.get("done_marker_found"))

    def _classify_completion(
        self,
        *,
        status: Optional[RunStatus],
        process_exit_code: Optional[int],
        done_info: Dict[str, Any],
        validation_warnings: List[str],
        terminal_error_code: Optional[str],
    ) -> Dict[str, Any]:
        done_signal_found = bool(done_info.get("done_signal_found"))
        done_marker_found = bool(done_info.get("done_marker_found"))
        marker_count = int(done_info.get("done_marker_count") or 0)
        diagnostics: List[str] = []
        if marker_count > 1:
            diagnostics.append("MULTIPLE_DONE_MARKERS_IGNORED")

        if done_signal_found:
            return {
                "state": "completed",
                "reason_code": "DONE_SIGNAL_FOUND",
                "diagnostics": diagnostics,
            }
        if process_exit_code is not None and int(process_exit_code) != 0:
            if done_marker_found:
                diagnostics.append("DONE_MARKER_PROCESS_FAILURE_CONFLICT")
            return {
                "state": "interrupted",
                "reason_code": "PROCESS_EXIT_NONZERO",
                "diagnostics": diagnostics,
            }
        if terminal_error_code == InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value:
            diagnostics.append(InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value)
            return {
                "state": "interrupted",
                "reason_code": InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value,
                "diagnostics": diagnostics,
            }
        if status == RunStatus.SUCCEEDED:
            if "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in validation_warnings:
                diagnostics.append("DONE_MARKER_MISSING")
                diagnostics.append("INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER")
                return {
                    "state": "completed",
                    "reason_code": "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER",
                    "diagnostics": diagnostics,
                }
            if done_marker_found:
                return {
                    "state": "completed",
                    "reason_code": "DONE_MARKER_FOUND",
                    "diagnostics": diagnostics,
                }
            return {
                "state": "completed",
                "reason_code": "OUTPUT_VALIDATED",
                "diagnostics": diagnostics,
            }
        if done_marker_found:
            return {
                "state": "completed",
                "reason_code": "DONE_MARKER_FOUND",
                "diagnostics": diagnostics,
            }
        if status == RunStatus.WAITING_USER:
            diagnostics.append("DONE_MARKER_MISSING")
            return {
                "state": "awaiting_user_input",
                "reason_code": "WAITING_USER_INPUT",
                "diagnostics": diagnostics,
            }
        if status in {RunStatus.FAILED, RunStatus.CANCELED}:
            return {
                "state": "interrupted",
                "reason_code": terminal_error_code or "TERMINAL_SIGNAL_FAILED",
                "diagnostics": diagnostics,
            }
        return {
            "state": "unknown",
            "reason_code": "INSUFFICIENT_EVIDENCE",
            "diagnostics": diagnostics,
        }

    def _write_attempt_audit_artifacts(
        self,
        *,
        run_dir: Path,
        run_id: str,
        request_id: Optional[str],
        engine_name: str,
        execution_mode: str,
        attempt_number: int,
        started_at: datetime,
        finished_at: datetime,
        status: Optional[RunStatus],
        fs_before_snapshot: Dict[str, Dict[str, Any]],
        process_exit_code: Optional[int],
        process_failure_reason: Optional[str],
        process_raw_stdout: str,
        process_raw_stderr: str,
        adapter: Any | None,
        turn_payload: Dict[str, Any],
        validation_warnings: List[str],
        terminal_error_code: Optional[str],
        options: Dict[str, Any],
    ) -> None:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        suffix = f".{attempt_number}"
        meta_path = audit_dir / f"meta{suffix}.json"
        stdin_path = audit_dir / f"stdin{suffix}.log"
        stdout_path = audit_dir / f"stdout{suffix}.log"
        stderr_path = audit_dir / f"stderr{suffix}.log"
        pty_output_path = audit_dir / f"pty-output{suffix}.log"
        fs_before_path = audit_dir / f"fs-before{suffix}.json"
        fs_after_path = audit_dir / f"fs-after{suffix}.json"
        fs_diff_path = audit_dir / f"fs-diff{suffix}.json"
        stdout_text = process_raw_stdout
        stderr_text = process_raw_stderr
        pty_text = f"{stdout_text}{stderr_text}"
        stdin_payload = options.get("__interactive_reply_payload")
        if stdin_payload is None:
            stdin_text = ""
        else:
            stdin_text = json.dumps(stdin_payload, ensure_ascii=False)

        stdin_path.write_text(stdin_text, encoding="utf-8")
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        pty_output_path.write_text(pty_text, encoding="utf-8")

        fs_after_snapshot = self._capture_filesystem_snapshot(run_dir)
        fs_diff = self._diff_filesystem_snapshot(fs_before_snapshot, fs_after_snapshot)
        fs_before_path.write_text(
            json.dumps(fs_before_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fs_after_path.write_text(
            json.dumps(fs_after_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fs_diff_path.write_text(
            json.dumps(fs_diff, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        done_info = self._find_done_markers(
            adapter=adapter,
            raw_stdout=stdout_text,
            raw_stderr=stderr_text,
            turn_payload=turn_payload,
        )
        completion = self._classify_completion(
            status=status,
            process_exit_code=process_exit_code,
            done_info=done_info,
            validation_warnings=validation_warnings,
            terminal_error_code=terminal_error_code,
        )

        reconstruction_error = None
        try:
            stdout_chunks = len(stdout_text.splitlines())
            stderr_chunks = len(stderr_text.splitlines())
        except Exception as exc:
            reconstruction_error = str(exc)
            stdout_chunks = 0
            stderr_chunks = 0

        status_text = status.value if isinstance(status, RunStatus) else (str(status) if status else "unknown")
        meta_payload = {
            "run_id": run_id,
            "request_id": request_id,
            "engine": engine_name,
            "execution_mode": execution_mode,
            "attempt": {"number": attempt_number},
            "status": status_text,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "process": {
                "exit_code": process_exit_code,
                "failure_reason": process_failure_reason,
            },
            "completion": {
                **completion,
                "done_signal_found": bool(done_info.get("done_signal_found")),
                "done_marker_found": bool(done_info.get("done_marker_found")),
                "done_marker_count": int(done_info.get("done_marker_count") or 0),
                "first_done_marker": done_info.get("first_marker"),
            },
            "validation_warnings": [str(item) for item in validation_warnings],
            "reconstruction_used": False,
            "stdout_chunks": stdout_chunks,
            "stderr_chunks": stderr_chunks,
            "reconstruction_error": reconstruction_error,
            "filesystem_diff": fs_diff,
        }
        meta_path.write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _append_orchestrator_event(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        category: str,
        type_name: str,
        data: Dict[str, Any],
    ) -> None:
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        event_path = audit_dir / f"orchestrator_events.{attempt_number}.jsonl"
        event_seq = self._next_orchestrator_event_seq(event_path)
        payload = make_orchestrator_event(
            attempt_number=attempt_number,
            seq=event_seq,
            category=category,
            type_name=type_name,
            data=data,
            ts=datetime.utcnow().isoformat(),
        )
        try:
            validate_orchestrator_event(payload)
        except ProtocolSchemaViolation as exc:
            raise RuntimeError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        with event_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False))
            fp.write("\n")

    def _next_orchestrator_event_seq(self, event_path: Path) -> int:
        if not event_path.exists() or not event_path.is_file():
            return 1
        max_seq = 0
        fallback_count = 0
        try:
            with event_path.open("r", encoding="utf-8") as fp:
                for line in fp:
                    if not line.strip():
                        continue
                    fallback_count += 1
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    seq_obj = payload.get("seq")
                    if isinstance(seq_obj, int) and seq_obj > max_seq:
                        max_seq = seq_obj
        except Exception:
            return max(1, fallback_count + 1)
        if max_seq > 0:
            return max_seq + 1
        return max(1, fallback_count + 1)

    def _append_internal_schema_warning(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        schema_path: str,
        detail: str,
    ) -> None:
        self._append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="diagnostic",
            type_name=OrchestratorEventType.DIAGNOSTIC_WARNING.value,
            data=make_diagnostic_warning_payload(
                code="SCHEMA_INTERNAL_INVALID",
                path=schema_path,
                detail=detail,
            ),
        )

    def _resolve_session_timeout_seconds(self, options: Dict[str, Any]) -> int:
        return resolve_session_timeout(
            options,
            default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
        ).value

    def _resolve_interactive_require_user_reply(
        self,
        *,
        options: Dict[str, Any],
        request_record: Dict[str, Any],
    ) -> bool:
        if "interactive_require_user_reply" in options:
            value = options.get("interactive_require_user_reply")
            if isinstance(value, bool):
                return value
        runtime_options = request_record.get("runtime_options", {})
        value = runtime_options.get("interactive_require_user_reply", True)
        return bool(value)

    def _resolve_interactive_profile(
        self,
        request_id: str,
        engine_name: str,
        options: Dict[str, Any],
    ) -> EngineInteractiveProfile:
        existing = run_store.get_interactive_profile(request_id)
        if existing:
            profile = EngineInteractiveProfile.model_validate(existing)
            if run_store.get_effective_session_timeout(request_id) is None:
                run_store.set_effective_session_timeout(request_id, profile.session_timeout_sec)
            return profile
        session_timeout_sec = self._resolve_session_timeout_seconds(options)
        profile = self.agent_cli_manager.resolve_interactive_profile(
            engine=engine_name,
            session_timeout_sec=session_timeout_sec,
        )
        run_store.set_effective_session_timeout(request_id, session_timeout_sec)
        run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        return profile

    def _inject_interactive_resume_context(
        self,
        request_id: str,
        profile: EngineInteractiveProfile,
        options: Dict[str, Any],
        run_dir: Path,
    ) -> None:
        if "__interactive_reply_payload" not in options:
            return
        interaction_id_raw = options.get("__interactive_reply_interaction_id", 0)
        try:
            interaction_id = int(interaction_id_raw)
        except Exception:
            interaction_id = 0
        resolution_mode_raw = options.get(
            "__interactive_resolution_mode",
            InteractiveResolutionMode.USER_REPLY.value,
        )
        resolution_mode = (
            str(resolution_mode_raw).strip()
            if resolution_mode_raw
            else InteractiveResolutionMode.USER_REPLY.value
        )
        resume_command = make_resume_command(
            interaction_id=max(1, interaction_id),
            response=options.get("__interactive_reply_payload"),
            resolution_mode=resolution_mode,
            auto_decide_reason=(
                str(options.get("__interactive_auto_reason"))
                if isinstance(options.get("__interactive_auto_reason"), str)
                else None
            ),
            auto_decide_policy=(
                str(options.get("__interactive_auto_policy"))
                if isinstance(options.get("__interactive_auto_policy"), str)
                else None
            ),
        )
        try:
            validate_resume_command(resume_command)
        except ProtocolSchemaViolation as exc:
            self._append_internal_schema_warning(
                run_dir=run_dir,
                attempt_number=self._resolve_attempt_number(request_id=request_id, is_interactive=True),
                schema_path="interactive_resume_command",
                detail=str(exc),
            )
            resume_command = make_resume_command(
                interaction_id=max(1, interaction_id),
                response=options.get("__interactive_reply_payload"),
                resolution_mode=InteractiveResolutionMode.USER_REPLY.value,
            )
        if interaction_id > 0:
            run_store.append_interaction_history(
                request_id=request_id,
                interaction_id=interaction_id,
                event_type="reply",
                payload={
                    "response": resume_command["response"],
                    "resolution_mode": resume_command["resolution_mode"],
                    "resolved_at": datetime.utcnow().isoformat(),
                    "auto_decide_reason": resume_command.get("auto_decide_reason"),
                    "auto_decide_policy": resume_command.get("auto_decide_policy"),
                },
            )
            run_store.consume_interaction_reply(request_id, interaction_id)
        options["__prompt_override"] = self._build_reply_prompt(
            resume_command.get("response")
        )
        handle = run_store.get_engine_session_handle(request_id)
        if not handle:
            raise RuntimeError(
                f"{InteractiveErrorCode.SESSION_RESUME_FAILED.value}: missing session handle"
            )
        options["__resume_session_handle"] = handle
        self._write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=run_store.get_pending_interaction(request_id) or {
                "interaction_id": interaction_id,
                "kind": "open_text",
                "prompt": "",
                "options": [],
                "ui_hints": {},
                "default_decision_policy": "engine_judgement",
                "required_fields": [],
            },
        )

    def _extract_pending_interaction(
        self,
        payload: Dict[str, Any],
        *,
        fallback_interaction_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        interaction_payload: Optional[Dict[str, Any]] = None
        if isinstance(payload.get("ask_user"), dict):
            interaction_payload = payload.get("ask_user")
        elif payload.get("action") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        elif payload.get("type") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        elif self._looks_like_direct_interaction_payload(payload):
            interaction_payload = payload
        if interaction_payload is None:
            return None

        ui_hints_raw = interaction_payload.get("ui_hints")
        ui_hints = ui_hints_raw if isinstance(ui_hints_raw, dict) else {}
        hint_obj = ui_hints.get("hint")
        hint_text = (
            self._normalize_interaction_prompt(hint_obj)
            if isinstance(hint_obj, str) and hint_obj.strip()
            else ""
        )
        prompt_obj = interaction_payload.get("prompt") or interaction_payload.get("question")
        prompt = (
            self._normalize_interaction_prompt(prompt_obj)
            if isinstance(prompt_obj, str) and prompt_obj.strip()
            else ""
        )
        if not prompt and hint_text:
            prompt = hint_text
        if not prompt:
            return None
        interaction_id = 0
        interaction_id_source = "payload"
        interaction_id_raw = interaction_payload.get("interaction_id")
        raw_interaction_id: Optional[str] = None
        if interaction_id_raw is not None:
            try:
                interaction_id = int(interaction_id_raw)
            except Exception:
                interaction_id = 0
                raw_interaction_id = str(interaction_id_raw).strip() or None
        if interaction_id <= 0 and fallback_interaction_id is not None and int(fallback_interaction_id) > 0:
            interaction_id = int(fallback_interaction_id)
            interaction_id_source = "fallback"
        if interaction_id <= 0:
            return None
        kind = self._normalize_interaction_kind_name(interaction_payload.get("kind"))
        options_payload = interaction_payload.get("options", [])
        options_normalized: list[dict[str, Any]] = []
        if isinstance(options_payload, list):
            for item in options_payload:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                options_normalized.append({"label": label, "value": item.get("value")})
        required_fields = interaction_payload.get("required_fields")
        if not isinstance(required_fields, list):
            required_fields = []
        default_decision_policy_raw = interaction_payload.get("default_decision_policy")
        default_decision_policy = (
            default_decision_policy_raw.strip()
            if isinstance(default_decision_policy_raw, str) and default_decision_policy_raw.strip()
            else "engine_judgement"
        )
        context_obj = interaction_payload.get("context")
        context: Optional[Dict[str, Any]]
        if isinstance(context_obj, dict):
            context = dict(context_obj)
        else:
            context = {}
        if raw_interaction_id:
            context["external_interaction_id"] = raw_interaction_id
        if interaction_id_source != "payload":
            context["interaction_id_source"] = interaction_id_source
        if not context:
            context = None
        return {
            "interaction_id": interaction_id,
            "kind": kind,
            "prompt": prompt,
            "options": options_normalized,
            "ui_hints": ui_hints,
            "default_decision_policy": default_decision_policy,
            "required_fields": required_fields,
            "context": context,
        }

    def _infer_pending_interaction(
        self,
        payload: Dict[str, Any],
        *,
        fallback_interaction_id: int,
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        outcome_obj = payload.get("outcome")
        if isinstance(outcome_obj, str) and outcome_obj.strip().lower() == "error":
            return None
        extracted = self._extract_pending_interaction(
            payload,
            fallback_interaction_id=fallback_interaction_id,
        )
        if extracted is not None:
            return extracted
        if fallback_interaction_id <= 0:
            return None
        prompt_obj = payload.get("prompt") or payload.get("question")
        ui_hints_obj = payload.get("ui_hints")
        hint_obj = ui_hints_obj.get("hint") if isinstance(ui_hints_obj, dict) else None
        hint = (
            self._normalize_interaction_prompt(hint_obj)
            if isinstance(hint_obj, str) and hint_obj.strip()
            else ""
        )
        prompt = (
            self._normalize_interaction_prompt(prompt_obj)
            if isinstance(prompt_obj, str) and prompt_obj.strip()
            else hint or "Please provide your reply to continue."
        )
        return {
            "interaction_id": int(fallback_interaction_id),
            "kind": "open_text",
            "prompt": prompt,
            "options": [],
            "ui_hints": {},
            "default_decision_policy": "engine_judgement",
            "required_fields": [],
            "context": {"inferred_from": "done_marker_missing"},
        }

    def _infer_pending_interaction_from_runtime_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: int,
    ) -> Optional[Dict[str, Any]]:
        if fallback_interaction_id <= 0:
            return None
        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
        except Exception:
            return None
        messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
        if not isinstance(messages, list) or not messages:
            return None
        latest_text = ""
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            text_obj = item.get("text")
            if isinstance(text_obj, str) and text_obj.strip():
                latest_text = self._normalize_interaction_prompt(text_obj)
                break
        if not latest_text:
            return None
        return {
            "interaction_id": int(fallback_interaction_id),
            "kind": "open_text",
            "prompt": latest_text,
            "options": [],
            "ui_hints": {},
            "default_decision_policy": "engine_judgement",
            "required_fields": [],
            "context": {"inferred_from": "runtime_stream_assistant_message"},
        }

    def _strip_prompt_yaml_blocks(self, text: str) -> str:
        normalized = text
        tag_pattern = re.compile(
            r"<ASK_USER_YAML>\s*[\s\S]*?\s*</ASK_USER_YAML>",
            re.IGNORECASE,
        )
        fence_pattern = re.compile(
            r"```(?:ask_user_yaml|ask-user-yaml)\s*[\s\S]*?```",
            re.IGNORECASE,
        )
        normalized = tag_pattern.sub("\n", normalized)
        normalized = fence_pattern.sub("\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized

    def _normalize_interaction_prompt(self, raw_prompt: Any) -> str:
        if not isinstance(raw_prompt, str):
            return ""
        normalized = self._strip_prompt_yaml_blocks(raw_prompt).strip()
        return normalized

    def _normalize_interaction_kind_name(self, raw_kind: Any) -> str:
        kind_name = str(raw_kind or "").strip().lower()
        alias_map = {
            "decision": "choose_one",
            "confirmation": "confirm",
            "clarification": "open_text",
        }
        kind_name = alias_map.get(kind_name, kind_name)
        allowed = {"choose_one", "confirm", "fill_fields", "open_text", "risk_ack"}
        if kind_name not in allowed:
            return "open_text"
        return kind_name

    def _looks_like_direct_interaction_payload(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        prompt_obj = payload.get("prompt") or payload.get("question")
        ui_hints_obj = payload.get("ui_hints")
        hint_obj = ui_hints_obj.get("hint") if isinstance(ui_hints_obj, dict) else None
        has_prompt = isinstance(prompt_obj, str) and bool(prompt_obj.strip())
        has_hint = isinstance(hint_obj, str) and bool(hint_obj.strip())
        if not has_prompt and not has_hint:
            return False
        if "interaction_id" in payload:
            return True
        if "kind" in payload:
            return True
        if isinstance(payload.get("options"), list):
            return True
        return False

    def _extract_pending_interaction_from_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        def _extract_from_text(text: str) -> Optional[Dict[str, Any]]:
            if not text.strip():
                return None
            snippets: List[str] = []
            tag_pattern = re.compile(
                r"<ASK_USER_YAML>\s*(.*?)\s*</ASK_USER_YAML>",
                re.IGNORECASE | re.DOTALL,
            )
            snippets.extend(match.group(1) for match in tag_pattern.finditer(text))
            fence_pattern = re.compile(
                r"```(?:ask_user_yaml|ask-user-yaml)\s*(.*?)```",
                re.IGNORECASE | re.DOTALL,
            )
            snippets.extend(match.group(1) for match in fence_pattern.finditer(text))
            for snippet in snippets:
                try:
                    parsed = yaml.safe_load(snippet)
                except Exception:
                    continue
                if not isinstance(parsed, dict):
                    continue
                extracted = self._extract_pending_interaction(
                    parsed,
                    fallback_interaction_id=fallback_interaction_id,
                )
                if extracted is not None:
                    return extracted
            return None

        # Prefer parser-extracted assistant text (decoded), because raw NDJSON logs
        # can contain escaped newlines that are not valid YAML for direct parsing.
        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=(raw_stdout or "").encode("utf-8", errors="replace"),
                stderr_raw=(raw_stderr or "").encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
            messages = parsed.get("assistant_messages") if isinstance(parsed, dict) else None
            if isinstance(messages, list):
                for item in reversed(messages):
                    if not isinstance(item, dict):
                        continue
                    text_obj = item.get("text")
                    if not isinstance(text_obj, str) or not text_obj.strip():
                        continue
                    extracted = _extract_from_text(text_obj)
                    if extracted is not None:
                        return extracted
        except Exception:
            pass

        stream_text = "\n".join(part for part in [raw_stdout or "", raw_stderr or ""] if isinstance(part, str))
        if not stream_text.strip():
            return None
        extracted = _extract_from_text(stream_text)
        if extracted is not None:
            return extracted
        return None

    def _strip_done_marker_for_output_validation(
        self,
        payload: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        if not isinstance(payload, dict):
            return {}, False
        marker_value = payload.get("__SKILL_DONE__")
        if "__SKILL_DONE__" not in payload:
            return dict(payload), False
        sanitized = dict(payload)
        sanitized.pop("__SKILL_DONE__", None)
        return sanitized, marker_value is True

    def _persist_waiting_interaction(
        self,
        *,
        adapter: Any,
        run_id: str,
        run_dir: Path,
        request_id: str,
        profile: EngineInteractiveProfile,
        interactive_require_user_reply: bool,
        pending_interaction: Dict[str, Any],
        raw_runtime_output: str,
    ) -> Optional[str]:
        attempt_number = self._resolve_attempt_number(
            request_id=request_id,
            is_interactive=True,
        )
        try:
            validate_pending_interaction(pending_interaction)
        except ProtocolSchemaViolation as exc:
            self._append_internal_schema_warning(
                run_dir=run_dir,
                attempt_number=attempt_number,
                schema_path="pending_interaction",
                detail=str(exc),
            )
            pending_interaction = {
                "interaction_id": int(pending_interaction.get("interaction_id", attempt_number)),
                "kind": "open_text",
                "prompt": (
                    self._normalize_interaction_prompt(pending_interaction.get("prompt"))
                    if isinstance(pending_interaction.get("prompt"), str)
                    else ""
                )
                or (
                    self._normalize_interaction_prompt(pending_interaction.get("ui_hints", {}).get("hint"))
                    if isinstance(pending_interaction.get("ui_hints"), dict)
                    and isinstance(pending_interaction.get("ui_hints", {}).get("hint"), str)
                    else ""
                )
                or "Please provide your reply to continue.",
                "options": [],
                "ui_hints": {},
                "default_decision_policy": "engine_judgement",
                "required_fields": [],
            }
        run_store.set_pending_interaction(request_id, pending_interaction)
        run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        run_store.append_interaction_history(
            request_id=request_id,
            interaction_id=int(pending_interaction["interaction_id"]),
            event_type="ask_user",
            payload=pending_interaction,
        )
        self._append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category="interaction",
            type_name=OrchestratorEventType.INTERACTION_USER_INPUT_REQUIRED.value,
            data={
                "interaction_id": int(pending_interaction["interaction_id"]),
                "kind": str(pending_interaction.get("kind", "open_text")),
            },
        )
        _ = run_id
        _ = interactive_require_user_reply
        try:
            handle = adapter.extract_session_handle(
                raw_runtime_output,
                turn_index=int(pending_interaction["interaction_id"]),
            )
        except Exception:
            return InteractiveErrorCode.SESSION_RESUME_FAILED.value
        run_store.set_engine_session_handle(
            request_id,
            handle.model_dump(mode="json"),
        )
        self._write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=pending_interaction,
        )
        return None

    def _write_interaction_mirror_files(
        self,
        *,
        run_dir: Path,
        request_id: str,
        pending_interaction: Dict[str, Any],
    ) -> None:
        interactions_dir = run_dir / "interactions"
        interactions_dir.mkdir(parents=True, exist_ok=True)
        (interactions_dir / "pending.json").write_text(
            json.dumps(pending_interaction, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        history = run_store.list_interaction_history(request_id)
        history_path = interactions_dir / "history.jsonl"
        with history_path.open("w", encoding="utf-8") as f:
            for item in history:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        runtime_state = {
            "interactive_profile": run_store.get_interactive_profile(request_id),
            "effective_session_timeout_sec": run_store.get_effective_session_timeout(request_id),
            "session_handle": run_store.get_engine_session_handle(request_id),
        }
        (interactions_dir / "runtime_state.json").write_text(
            json.dumps(runtime_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def _auto_decide_after_timeout(
        self,
        *,
        request_id: str,
        run_id: str,
        delay_sec: int,
    ) -> None:
        await asyncio.sleep(max(1, int(delay_sec)))
        request_record = run_store.get_request(request_id)
        if not request_record or request_record.get("run_id") != run_id:
            return
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            return
        status_file = run_dir / "status.json"
        if not status_file.exists():
            return
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        current_status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        if current_status != RunStatus.WAITING_USER:
            return
        pending_interaction = run_store.get_pending_interaction(request_id)
        if pending_interaction is None:
            return
        runtime_options = request_record.get("runtime_options", {})
        interactive_require_user_reply = bool(
            runtime_options.get("interactive_require_user_reply", True)
        )
        if not timeout_requires_auto_decision(interactive_require_user_reply):
            return
        await self._resume_with_auto_decision(
            request_record=request_record,
            run_id=run_id,
            request_id=request_id,
            pending_interaction=pending_interaction,
        )

    async def _resume_with_auto_decision(
        self,
        *,
        request_record: Dict[str, Any],
        run_id: str,
        request_id: str,
        pending_interaction: Dict[str, Any],
    ) -> None:
        interaction_id_obj = pending_interaction.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            interaction_id = interaction_id_obj
        elif isinstance(interaction_id_obj, str):
            try:
                interaction_id = int(interaction_id_obj)
            except ValueError:
                return
        else:
            return
        if interaction_id <= 0:
            return

        default_policy_obj = pending_interaction.get("default_decision_policy")
        default_policy = (
            default_policy_obj.strip()
            if isinstance(default_policy_obj, str) and default_policy_obj.strip()
            else "engine_judgement"
        )
        auto_reply_payload = {
            "source": "auto_decide_timeout",
            "interaction_id": interaction_id,
            "reason": "user_no_reply",
            "policy": default_policy,
            "instruction": (
                "User did not respond in time. Continue with your best judgement "
                "based on the current context."
            ),
        }
        resume_command = make_resume_command(
            interaction_id=interaction_id,
            response=auto_reply_payload,
            resolution_mode=InteractiveResolutionMode.AUTO_DECIDE_TIMEOUT.value,
            auto_decide_reason="user_no_reply",
            auto_decide_policy=default_policy,
        )
        try:
            validate_resume_command(resume_command)
        except ProtocolSchemaViolation as exc:
            self._append_internal_schema_warning(
                run_dir=workspace_manager.get_run_dir(run_id) or Path(config.SYSTEM.RUNS_DIR) / run_id,
                attempt_number=self._resolve_attempt_number(request_id=request_id, is_interactive=True),
                schema_path="interactive_resume_command",
                detail=str(exc),
            )
            resume_command = make_resume_command(
                interaction_id=interaction_id,
                response=auto_reply_payload,
                resolution_mode=InteractiveResolutionMode.USER_REPLY.value,
            )
        reply_state = run_store.submit_interaction_reply(
            request_id=request_id,
            interaction_id=interaction_id,
            response=resume_command["response"],
            idempotency_key=f"auto-timeout:{interaction_id}",
        )
        if reply_state not in {"accepted", "idempotent"}:
            return

        next_status = waiting_reply_target_status()
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            return
        self._update_status(
            run_dir,
            next_status,
            effective_session_timeout_sec=run_store.get_effective_session_timeout(request_id),
        )
        run_store.update_run_status(run_id, next_status)

        options = {
            **request_record.get("engine_options", {}),
            **request_record.get("runtime_options", {}),
            "__interactive_reply_payload": resume_command["response"],
            "__interactive_reply_interaction_id": resume_command["interaction_id"],
            "__interactive_resolution_mode": resume_command["resolution_mode"],
            "__interactive_auto_reason": resume_command.get("auto_decide_reason"),
            "__interactive_auto_policy": resume_command.get("auto_decide_policy"),
        }
        await self.run_job(
            run_id=run_id,
            skill_id=str(request_record["skill_id"]),
            engine_name=str(request_record["engine"]),
            options=options,
            cache_key=None,
        )

    async def recover_incomplete_runs_on_startup(self) -> None:
        records = run_store.list_incomplete_runs()
        if not records:
            concurrency_manager.reset_runtime_state()
            return

        for record in records:
            await self._recover_single_incomplete_run(record)

        await self._cleanup_orphan_runtime_bindings(records)
        active_run_dirs: list[Path] = []
        for run_id in run_store.list_active_run_ids():
            run_dir = workspace_manager.get_run_dir(run_id)
            if run_dir:
                active_run_dirs.append(run_dir)
        try:
            run_folder_trust_manager.cleanup_stale_entries(active_run_dirs)
        except Exception:
            logger.warning("Startup stale trust cleanup failed", exc_info=True)
        concurrency_manager.reset_runtime_state()

    async def _recover_single_incomplete_run(self, record: Dict[str, Any]) -> None:
        request_id = str(record.get("request_id") or "")
        run_id = str(record.get("run_id") or "")
        run_status_raw = record.get("run_status")
        engine_name = str(record.get("engine") or "")
        if not request_id or not run_id or not isinstance(run_status_raw, str):
            return
        try:
            run_status = RunStatus(run_status_raw)
        except ValueError:
            return

        if run_status == RunStatus.WAITING_USER:
            pending = run_store.get_pending_interaction(request_id)
            handle = run_store.get_engine_session_handle(request_id)
            recovery_event = waiting_recovery_event(
                has_pending_interaction=isinstance(pending, dict),
                has_valid_handle=self._is_valid_session_handle(handle),
            )
            if recovery_event == SessionEvent.RESTART_PRESERVE_WAITING:
                run_store.update_run_status(run_id, RunStatus.WAITING_USER)
                run_store.set_recovery_info(
                    run_id,
                    recovery_state="recovered_waiting",
                    recovery_reason="resumable_waiting_preserved",
                )
                return
            await self._mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                reason="missing pending interaction or session handle after restart",
            )
            return

        if run_status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            await self._mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
                reason=f"{run_status.value} run interrupted by orchestrator restart",
            )

    async def _mark_restart_reconciled_failed(
        self,
        *,
        request_id: str,
        run_id: str,
        engine_name: str,
        error_code: str,
        reason: str,
    ) -> None:
        message = f"{error_code}: {reason}"
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir:
            self._update_status(
                run_dir,
                RunStatus.FAILED,
                error={"code": error_code, "message": message},
                effective_session_timeout_sec=run_store.get_effective_session_timeout(request_id),
            )
        run_store.update_run_status(run_id, RunStatus.FAILED)
        run_store.set_recovery_info(
            run_id,
            recovery_state="failed_reconciled",
            recovery_reason=reason,
        )
        run_store.clear_pending_interaction(request_id)
        run_store.clear_engine_session_handle(request_id)
        adapter = self.adapters.get(engine_name)
        if adapter is not None:
            with contextlib.suppress(Exception):
                await adapter.cancel_run_process(run_id)

    async def _cleanup_orphan_runtime_bindings(self, records: List[Dict[str, Any]]) -> None:
        _ = records

    def _is_valid_session_handle(self, handle: Any) -> bool:
        if not isinstance(handle, dict):
            return False
        try:
            parsed = EngineSessionHandle.model_validate(handle)
        except Exception:
            return False
        return bool(parsed.handle_value)

    def _build_reply_prompt(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False)

    def _error_from_exception(self, exc: Exception) -> Dict[str, Any]:
        if isinstance(exc, ProtocolSchemaViolation):
            return {
                "code": InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value,
                "message": (
                    f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
                ),
            }
        text = str(exc)
        for code in (
            InteractiveErrorCode.SESSION_RESUME_FAILED.value,
            InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
            InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value,
        ):
            if text.startswith(code):
                return {"code": code, "message": text}
        return {"message": text}

job_orchestrator = JobOrchestrator()

logger = logging.getLogger(__name__)
