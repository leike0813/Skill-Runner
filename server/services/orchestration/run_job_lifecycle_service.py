from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.models import (
    DispatchPhase,
    EngineInteractiveProfile,
    ExecutionMode,
    InteractiveErrorCode,
    OrchestratorEventType,
    PendingOwner,
    RunStatus,
    SkillManifest,
)
from server.runtime.logging.run_context import bind_run_logging_context
from server.runtime.logging.structured_trace import log_event
from server.runtime.auth_detection.types import AuthDetectionResult
from server.runtime.protocol.factories import make_diagnostic_warning_payload
from server.runtime.protocol.live_publish import LiveRuntimeEmitterImpl
from server.runtime.session.statechart import timeout_requires_auto_decision
from server.services.orchestration.run_execution_core import resolve_conversation_mode
from server.services.orchestration.run_audit_contract_service import run_audit_contract_service
from server.services.orchestration.run_service_log_mirror import RunServiceLogMirrorSession
from server.services.orchestration.run_projection_service import run_projection_service
from server.services.orchestration.run_skill_materialization_service import run_folder_bootstrapper
from server.services.platform.async_compat import maybe_await
from server.services.platform.schema_validator import schema_validator
from server.services.skill.skill_registry import skill_registry

logger = logging.getLogger(__name__)


def _normalize_opencode_provider(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _provider_from_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if "/" not in normalized:
        return None
    provider, _rest = normalized.split("/", 1)
    return _normalize_opencode_provider(provider)


def _resolve_opencode_provider_from_model(
    *,
    engine_name: str,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str | None:
    if engine_name.strip().lower() != "opencode":
        return None
    request_payload = request_record if isinstance(request_record, dict) else {}
    engine_options = request_payload.get("engine_options")
    effective_runtime_options = request_payload.get("effective_runtime_options")
    runtime_options = request_payload.get("runtime_options")
    for candidate in (
        engine_options.get("model") if isinstance(engine_options, dict) else None,
        options.get("model"),
        effective_runtime_options.get("model")
        if isinstance(effective_runtime_options, dict)
        else None,
        runtime_options.get("model") if isinstance(runtime_options, dict) else None,
    ):
        provider_id = _provider_from_model(candidate)
        if provider_id is not None:
            return provider_id
    return None


def _opencode_provider_unresolved_detail(
    *,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str:
    request_payload = request_record if isinstance(request_record, dict) else {}
    engine_options = request_payload.get("engine_options")
    effective_runtime_options = request_payload.get("effective_runtime_options")
    runtime_options = request_payload.get("runtime_options")
    raw_model = None
    for candidate in (
        engine_options.get("model") if isinstance(engine_options, dict) else None,
        options.get("model"),
        effective_runtime_options.get("model")
        if isinstance(effective_runtime_options, dict)
        else None,
        runtime_options.get("model") if isinstance(runtime_options, dict) else None,
    ):
        if isinstance(candidate, str) and candidate.strip():
            raw_model = candidate.strip()
            break
    if raw_model is None:
        return "opencode provider could not be resolved because engine_options.model is missing"
    return (
        "opencode provider could not be resolved from engine_options.model="
        f"{raw_model!r}"
    )


def _adapter_accepts_live_runtime_emitter(adapter: Any) -> bool:
    run_callable = getattr(adapter, "run", None)
    if run_callable is None:
        return False
    try:
        signature = inspect.signature(run_callable)
    except (TypeError, ValueError):
        return False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == "live_runtime_emitter":
            return True
    return False


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
            - Updates `.state/state.json` and `.state/dispatch.json` in run_dir.
            - Writes '.audit/stdout.{attempt}.log', '.audit/stderr.{attempt}.log'.
            - Writes 'result/result.json'.
        """
        slot_acquired = False
        release_slot_on_exit = True
        run_dir: Path | None = None
        run_log_mirror_stack: contextlib.ExitStack | None = None
        run_store = self._run_store_backend()
        workspace_manager = self._workspace_backend()
        concurrency_manager = self._concurrency_backend()
        run_folder_trust_manager = self._trust_manager_backend()
        await concurrency_manager.acquire_slot()
        slot_acquired = True
        log_event(
            logger,
            event="run.lifecycle.slot_acquired",
            phase="run_lifecycle",
            outcome="ok",
            request_id=None,
            run_id=run_id,
            engine=engine_name,
        )
        try:
            run_dir = workspace_manager.get_run_dir(run_id)
            if not run_dir:
                log_event(
                    logger,
                    event="run.lifecycle.failed",
                    phase="run_lifecycle",
                    outcome="error",
                    level=logging.ERROR,
                    request_id=None,
                    run_id=run_id,
                    engine=engine_name,
                    error_code="RUN_DIR_NOT_FOUND",
                )
                return RunJobOutcome(run_id=run_id)
            request_record = await run_store.get_request_by_run_id(run_id)
            request_id = request_record.get("request_id") if request_record else None
            effective_runtime_options = (
                request_record.get("effective_runtime_options", {})
                if isinstance(request_record, dict)
                else {}
            )
            execution_mode = str(
                options.get(
                    "execution_mode",
                    effective_runtime_options.get(
                        "execution_mode",
                        (request_record or {}).get("runtime_options", {}).get(
                        "execution_mode", ExecutionMode.AUTO.value
                        ),
                    ),
                )
            )
            conversation_mode = resolve_conversation_mode(
                (request_record or {}).get("client_metadata")
            )
            session_capable = conversation_mode == "session"
            is_interactive = execution_mode == ExecutionMode.INTERACTIVE.value
            interactive_auto_reply = self._resolve_interactive_auto_reply(
                options=options,
                request_record=request_record or {},
            )
            can_wait_for_user = is_interactive and session_capable
            interactive_profile: Optional[EngineInteractiveProfile] = None
            if can_wait_for_user and request_id:
                interactive_profile = await self._resolve_interactive_profile(
                    request_id=request_id,
                    engine_name=engine_name,
                    options=options,
                )
            attempt_override_obj = options.get("__attempt_number_override")
            if isinstance(attempt_override_obj, int) and attempt_override_obj > 0:
                attempt_number = attempt_override_obj
            else:
                attempt_number = await self._resolve_attempt_number(
                    request_id=request_id,
                    is_interactive=is_interactive,
                )
            resume_ticket_id = (
                str(options.get("__resume_ticket_id"))
                if isinstance(options.get("__resume_ticket_id"), str) and str(options.get("__resume_ticket_id")).strip()
                else None
            )
            if request_id and resume_ticket_id is not None:
                resume_started = await maybe_await(
                    run_store.mark_resume_ticket_started(
                        request_id,
                        resume_ticket_id,
                        target_attempt=attempt_number,
                    )
                )
                if not resume_started:
                    log_event(
                        logger,
                        event="run.lifecycle.failed",
                        phase="run_lifecycle",
                        outcome="error",
                        level=logging.WARNING,
                        request_id=request_id,
                        run_id=run_id,
                        attempt=attempt_number,
                        engine=engine_name,
                        error_code="RESUME_TICKET_NOT_OWNED",
                    )
                    return RunJobOutcome(run_id=run_id)
            if request_id:
                await run_projection_service.claim_dispatch(
                    run_dir=run_dir,
                    request_id=request_id,
                    run_id=run_id,
                    run_store_backend=run_store,
                )
                await run_projection_service.advance_dispatch_phase(
                    run_dir=run_dir,
                    request_id=request_id,
                    run_id=run_id,
                    phase=DispatchPhase.ATTEMPT_MATERIALIZING,
                    run_store_backend=run_store,
                )
                run_audit_contract_service.initialize_attempt_audit(
                    run_dir=run_dir,
                    request_id=request_id,
                    attempt_number=attempt_number,
                    status=RunStatus.QUEUED.value,
                    engine=engine_name,
                    skill_id=skill_id,
                )
            run_audit_contract_service.initialize_run_audit(run_dir=run_dir)
            run_log_mirror_stack = contextlib.ExitStack()
            run_log_mirror_stack.enter_context(
                bind_run_logging_context(
                    run_id=run_id,
                    request_id=request_id,
                    attempt_number=attempt_number,
                    phase="run_lifecycle",
                )
            )
            run_log_mirror_stack.enter_context(
                RunServiceLogMirrorSession.open_run_scope(
                    run_dir=run_dir,
                    run_id=run_id,
                )
            )
            run_log_mirror_stack.enter_context(
                RunServiceLogMirrorSession.open_attempt_scope(
                    run_dir=run_dir,
                    run_id=run_id,
                    attempt_number=attempt_number,
                )
            )
            logger.info(
                "run_attempt_started run_id=%s request_id=%s attempt=%s engine=%s mode=%s",
                run_id,
                request_id,
                attempt_number,
                engine_name,
                execution_mode,
            )
            log_event(
                logger,
                event="run.lifecycle.resumed" if attempt_number > 1 else "run.lifecycle.started",
                phase="run_lifecycle",
                outcome="start",
                request_id=request_id,
                run_id=run_id,
                attempt=attempt_number,
                engine=engine_name,
                execution_mode=execution_mode,
            )
            attempt_started_at = datetime.utcnow()
            fs_before_snapshot = self._capture_filesystem_snapshot(run_dir)
            process_exit_code: Optional[int] = None
            process_failure_reason: Optional[str] = None
            process_raw_stdout = ""
            process_raw_stderr = ""
            runtime_parse_result: dict[str, Any] | None = None
            auth_detection_result = AuthDetectionResult(
                classification="unknown",
                subcategory=None,
                confidence="low",
                engine=engine_name,
                evidence_sources=[],
                details={},
            )
            turn_payload_for_completion: Dict[str, Any] = {}
            done_signal_found_in_payload = False
            auth_session_meta: Dict[str, Any] | None = None
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
                run_dir=run_dir,
                status=RunStatus.RUNNING,
                effective_session_timeout_sec=(
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                ),
            )
            if request_id:
                await run_projection_service.write_non_terminal_projection(
                    run_dir=run_dir,
                    request_id=request_id,
                    run_id=run_id,
                    status=RunStatus.RUNNING,
                    request_record=request_record,
                    current_attempt=attempt_number,
                    pending_owner=None,
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                    run_store_backend=run_store,
                )
            self._append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="lifecycle",
                type_name=OrchestratorEventType.LIFECYCLE_RUN_STARTED.value,
                data={"status": RunStatus.RUNNING.value},
                engine_name=engine_name,
            )
            self._update_latest_run_id(run_id)

            try:
                # 2. Get Skill
                skill = skill_override
                if skill is None:
                    skill = run_folder_bootstrapper.load_from_snapshot(
                        run_dir=run_dir,
                        skill_id=skill_id,
                        engine_name=engine_name,
                    )
                if skill is None:
                    skill = skill_registry.get_skill(skill_id)
                if skill is None and is_interactive:
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
                input_data = {
                    "input": dict((request_record or {}).get("input") or {}),
                    "parameter": dict((request_record or {}).get("parameter") or {}),
                }

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
                if request_id:
                    run_options["__request_id"] = request_id
                run_options["__engine_name"] = engine_name
                if is_interactive and request_id and interactive_profile:
                    await self._inject_interactive_resume_context(
                        request_id=request_id,
                        profile=interactive_profile,
                        options=run_options,
                        run_dir=run_dir,
                    )

                # 5. Execute
                adapter_stream_parser = getattr(adapter, "stream_parser", adapter)
                live_runtime_emitter = LiveRuntimeEmitterImpl(
                    run_id=run_id,
                    run_dir=run_dir,
                    engine=engine_name,
                    attempt_number=attempt_number,
                    stream_parser=adapter_stream_parser,
                )
                try:
                    logger.info(
                        "run_attempt_execute_begin run_id=%s request_id=%s attempt=%s engine=%s",
                        run_id,
                        request_id,
                        attempt_number,
                        engine_name,
                    )
                    if _adapter_accepts_live_runtime_emitter(adapter):
                        result = await adapter.run(
                            skill,
                            input_data,
                            run_dir,
                            run_options,
                            live_runtime_emitter=live_runtime_emitter,
                        )
                    else:
                        result = await adapter.run(
                            skill,
                            input_data,
                            run_dir,
                            run_options,
                        )
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
                logger.info(
                    "run_attempt_execute_end run_id=%s request_id=%s attempt=%s exit_code=%s failure_reason=%s",
                    run_id,
                    request_id,
                    attempt_number,
                    process_exit_code,
                    process_failure_reason,
                )
                process_raw_stdout = result.raw_stdout or ""
                process_raw_stderr = result.raw_stderr or ""
                runtime_parse_result = self._parse_runtime_stream_for_auth_detection(
                    adapter=adapter,
                    raw_stdout=process_raw_stdout,
                    raw_stderr=process_raw_stderr,
                )
                auth_detection_result = self.auth_detection_service.detect(
                    engine=engine_name,
                    raw_stdout=process_raw_stdout,
                    raw_stderr=process_raw_stderr,
                    pty_output=f"{process_raw_stdout}{process_raw_stderr}",
                    runtime_parse_result=runtime_parse_result,
                )
                auth_detection_high = (
                    auth_detection_result.detected
                    and auth_detection_result.confidence == "high"
                )
                if await run_store.is_cancel_requested(run_id):
                    raise RunCanceled()

                # 6. Verify Result and Normalize
                warnings: list[str] = []
                output_data: Dict[str, Any] = {}
                schema_output_errors: list[str] = []
                terminal_validation_errors: list[str] = []
                pending_interaction: Optional[Dict[str, Any]] = None
                pending_interaction_candidate: Optional[Dict[str, Any]] = None
                pending_auth_method_selection: Optional[Dict[str, Any]] = None
                pending_auth: Optional[Dict[str, Any]] = None
                repair_level = result.repair_level or "none"
                has_structured_output = False
                structured_output_payload = self._resolve_structured_output_payload(
                    result=result,
                    runtime_parse_result=runtime_parse_result,
                )
                if isinstance(structured_output_payload, dict):
                    turn_payload_for_completion = dict(structured_output_payload)
                done_marker_found_in_stream = self._contains_done_marker_in_stream(
                    adapter=adapter,
                    raw_stdout=result.raw_stdout,
                    raw_stderr=result.raw_stderr,
                )
                done_signal_found = done_marker_found_in_stream
                if result.exit_code == 0:
                    if isinstance(structured_output_payload, dict):
                        has_structured_output = True
                        output_data, done_signal_found_in_payload = (
                            self._strip_done_marker_for_output_validation(structured_output_payload)
                        )
                        done_signal_found = (
                            done_signal_found_in_payload or done_marker_found_in_stream
                        )
                        schema_output_errors = schema_validator.validate_output(skill, output_data)
                        if not schema_output_errors and repair_level == "deterministic_generic":
                            warnings.append("OUTPUT_REPAIRED_GENERIC")
                    else:
                        schema_output_errors = ["Output JSON missing or unreadable"]

                if can_wait_for_user and not done_signal_found and not auth_detection_high:
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
                elif is_interactive and not done_signal_found and not auth_detection_high:
                    pending_interaction_candidate = self._extract_pending_interaction(
                        output_data,
                        fallback_interaction_id=attempt_number,
                    )
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
                    if (
                        pending_interaction_candidate is not None
                        and request_id
                        and run_id
                        and not session_capable
                        and interactive_auto_reply
                    ):
                        pending_interaction_candidate.setdefault("source_attempt", attempt_number)
                        await maybe_await(
                            run_store.set_pending_interaction(
                                request_id,
                                pending_interaction_candidate,
                            )
                        )
                        await maybe_await(
                            run_store.append_interaction_history(
                                request_id=request_id,
                                interaction_id=int(pending_interaction_candidate["interaction_id"]),
                                event_type="ask_user",
                                payload=pending_interaction_candidate,
                                source_attempt=attempt_number,
                            )
                        )
                        await run_projection_service.write_non_terminal_projection(
                            run_dir=run_dir,
                            request_id=request_id,
                            run_id=run_id,
                            status=RunStatus.QUEUED,
                            request_record=request_record,
                            current_attempt=attempt_number,
                            pending_owner=None,
                            source_attempt=attempt_number,
                            target_attempt=attempt_number + 1,
                            run_store_backend=run_store,
                        )
                        await run_store.update_run_status(run_id, RunStatus.QUEUED)
                        asyncio.create_task(
                            self._resume_with_auto_decision(
                                request_record=request_record or {},
                                run_id=run_id,
                                request_id=request_id,
                                pending_interaction=pending_interaction_candidate,
                            )
                        )
                        final_status = RunStatus.QUEUED
                        final_validation_warnings = list(warnings)
                        return RunJobOutcome(run_id=run_id, final_status=RunStatus.QUEUED)

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
                if auth_detection_high and session_capable and request_id:
                    canonical_provider_id = _resolve_opencode_provider_from_model(
                        engine_name=engine_name,
                        options=options,
                        request_record=request_record,
                    )
                    created_pending_auth = await self.auth_orchestration_service.create_pending_auth(
                        run_id=run_id,
                        run_dir=run_dir,
                        request_id=request_id,
                        skill_id=skill_id,
                        engine_name=engine_name,
                        options=options,
                        attempt_number=attempt_number,
                        auth_detection=auth_detection_result,
                        canonical_provider_id=canonical_provider_id,
                        run_store_backend=run_store,
                        append_orchestrator_event=self._append_orchestrator_event,
                        update_status=self._update_status,
                    )
                    if created_pending_auth is not None:
                        created_pending_payload = created_pending_auth.model_dump(mode="json")
                        if "auth_session_id" in created_pending_payload:
                            pending_auth = created_pending_payload
                            auth_session_meta = {
                                "session_id": created_pending_payload.get("auth_session_id"),
                                "engine": created_pending_payload.get("engine"),
                                "provider_id": created_pending_payload.get("provider_id"),
                                "challenge_kind": created_pending_payload.get("challenge_kind"),
                                "status": "waiting",
                                "source_attempt": attempt_number,
                                "resume_attempt": None,
                                "last_error": created_pending_payload.get("last_error"),
                                "redacted_submission": {"kind": None, "present": False},
                            }
                        else:
                            pending_auth_method_selection = created_pending_payload
                        forced_failure_reason = None
                    else:
                        if (
                            engine_name.strip().lower() == "opencode"
                            and canonical_provider_id is None
                        ):
                            warning_code = "OPENCODE_PROVIDER_UNRESOLVED_FROM_MODEL"
                            warnings.append(warning_code)
                            self._append_orchestrator_event(
                                run_dir=run_dir,
                                attempt_number=attempt_number,
                                category="diagnostic",
                                type_name=OrchestratorEventType.DIAGNOSTIC_WARNING.value,
                                data=make_diagnostic_warning_payload(
                                    code=warning_code,
                                    detail=_opencode_provider_unresolved_detail(
                                        options=options,
                                        request_record=request_record,
                                    ),
                                ),
                                engine_name=engine_name,
                            )
                        forced_failure_reason = "AUTH_REQUIRED"
                elif auth_detection_high:
                    forced_failure_reason = "AUTH_REQUIRED"
                elif result.failure_reason in {
                    "AUTH_REQUIRED",
                    "TIMEOUT",
                    InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                }:
                    forced_failure_reason = result.failure_reason
                else:
                    forced_failure_reason = None

                normalized_status = "success"
                if pending_auth is not None or pending_auth_method_selection is not None:
                    normalized_status = RunStatus.WAITING_AUTH.value
                elif forced_failure_reason or result.exit_code != 0:
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
                        elif can_wait_for_user:
                            normalized_status = RunStatus.WAITING_USER.value
                            pending_interaction = pending_interaction_candidate
                        else:
                            forced_failure_reason = "NON_SESSION_INTERACTIVE_REPLY_UNSUPPORTED"
                            normalized_status = "failed"
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
                        attempt_number=attempt_number,
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
                elif normalized_status == RunStatus.WAITING_AUTH.value:
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
                    elif forced_failure_reason == "NON_SESSION_INTERACTIVE_REPLY_UNSUPPORTED":
                        error_code = forced_failure_reason
                        error_message = (
                            "Client conversation_mode=non_session cannot enter waiting_user; "
                            "interactive flow must auto-resolve without waiting."
                        )
                    elif has_output_error:
                        error_message = "; ".join(terminal_validation_errors)
                    else:
                        error_message = f"Exit code {result.exit_code}"
                    normalized_error = {
                        "code": error_code,
                        "message": error_message,
                        "stderr": result.raw_stderr,
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

                # 7. Finalize status and bundles
                if normalized_status == "success":
                    final_status = RunStatus.SUCCEEDED
                elif normalized_status == RunStatus.WAITING_USER.value:
                    final_status = RunStatus.WAITING_USER
                elif normalized_status == RunStatus.WAITING_AUTH.value:
                    final_status = RunStatus.WAITING_AUTH
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
                effective_session_timeout_sec = (
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                )
                projection_request_id = request_id or f"run:{run_id}"
                if final_status == RunStatus.WAITING_USER and pending_interaction is not None:
                    logger.info(
                        "run_attempt_waiting_user run_id=%s request_id=%s attempt=%s interaction_id=%s",
                        run_id,
                        projection_request_id,
                        attempt_number,
                        pending_interaction.get("interaction_id"),
                    )
                    await run_projection_service.write_non_terminal_projection(
                        run_dir=run_dir,
                        request_id=projection_request_id,
                        run_id=run_id,
                        status=RunStatus.WAITING_USER,
                        request_record=request_record,
                        current_attempt=attempt_number,
                        pending_owner=PendingOwner.WAITING_USER,
                        pending_interaction=pending_interaction,
                        source_attempt=attempt_number,
                        effective_session_timeout_sec=effective_session_timeout_sec,
                        warnings=warnings,
                        error=None,
                        run_store_backend=run_store,
                    )
                    await run_store.update_run_status(run_id, final_status)
                    log_event(
                        logger,
                        event="run.lifecycle.waiting_user",
                        phase="run_lifecycle",
                        outcome="ok",
                        request_id=request_id,
                        run_id=run_id,
                        attempt=attempt_number,
                        engine=engine_name,
                        interaction_id=pending_interaction.get("interaction_id"),
                    )
                elif final_status == RunStatus.WAITING_AUTH:
                    logger.info(
                        "run_attempt_waiting_auth run_id=%s request_id=%s attempt=%s",
                        run_id,
                        projection_request_id,
                        attempt_number,
                    )
                    pending_owner = None
                    if pending_auth_method_selection is not None:
                        pending_owner = PendingOwner.WAITING_AUTH_METHOD_SELECTION
                    elif pending_auth is not None:
                        pending_owner = PendingOwner.WAITING_AUTH_CHALLENGE
                    await run_projection_service.write_non_terminal_projection(
                        run_dir=run_dir,
                        request_id=projection_request_id,
                        run_id=run_id,
                        status=RunStatus.WAITING_AUTH,
                        request_record=request_record,
                        current_attempt=attempt_number,
                        pending_owner=pending_owner,
                        pending_auth_method_selection=pending_auth_method_selection,
                        pending_auth=pending_auth,
                        source_attempt=attempt_number,
                        effective_session_timeout_sec=effective_session_timeout_sec,
                        warnings=warnings,
                        error=None,
                        run_store_backend=run_store,
                    )
                    await run_store.update_run_status(run_id, final_status)
                    log_event(
                        logger,
                        event="run.lifecycle.waiting_auth",
                        phase="run_lifecycle",
                        outcome="ok",
                        request_id=request_id,
                        run_id=run_id,
                        attempt=attempt_number,
                        engine=engine_name,
                    )
                else:
                    logger.info(
                        "run_attempt_terminal run_id=%s request_id=%s attempt=%s status=%s",
                        run_id,
                        projection_request_id,
                        attempt_number,
                        final_status.value,
                    )
                    await run_projection_service.write_terminal_projection(
                        run_dir=run_dir,
                        request_id=projection_request_id,
                        run_id=run_id,
                        status=final_status,
                        request_record=request_record,
                        current_attempt=attempt_number,
                        effective_session_timeout_sec=effective_session_timeout_sec,
                        warnings=warnings,
                        error=normalized_error,
                        terminal_result={
                            "data": output_data if final_status == RunStatus.SUCCEEDED else None,
                            "artifacts": artifacts,
                            "repair_level": repair_level,
                            "validation_warnings": warnings,
                            "error": normalized_error,
                        },
                        run_store_backend=run_store,
                    )
                    result_path = run_dir / "result" / "result.json"
                    await run_store.update_run_status(run_id, final_status, str(result_path))
                    log_event(
                        logger,
                        event=(
                            "run.lifecycle.succeeded"
                            if final_status == RunStatus.SUCCEEDED
                            else "run.lifecycle.failed"
                        ),
                        phase="run_lifecycle",
                        outcome="ok" if final_status == RunStatus.SUCCEEDED else "error",
                        level=logging.INFO if final_status == RunStatus.SUCCEEDED else logging.ERROR,
                        request_id=request_id,
                        run_id=run_id,
                        attempt=attempt_number,
                        engine=engine_name,
                        error_code=final_error_code,
                    )
                    self._build_run_bundle(run_dir, debug=False)
                    self._build_run_bundle(run_dir, debug=True)
                if final_status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}:
                    self._append_orchestrator_event(
                        run_dir=run_dir,
                        attempt_number=attempt_number,
                        category="lifecycle",
                        type_name=OrchestratorEventType.LIFECYCLE_RUN_TERMINAL.value,
                        data={"status": final_status.value},
                        engine_name=engine_name,
                    )
                if cache_key and final_status == RunStatus.SUCCEEDED:
                    skill_source = (
                        str((request_record or {}).get("skill_source") or "installed")
                        if isinstance(request_record, dict)
                        else "installed"
                    )
                    if skill_source == "temp_upload":
                        await run_store.record_temp_cache_entry(cache_key, run_id)
                    else:
                        await run_store.record_cache_entry(cache_key, run_id)

            except RunCanceled:
                final_status = RunStatus.CANCELED
                canceled_error = self._build_canceled_error()
                normalized_error_message = canceled_error["message"]
                final_error_code = str(canceled_error.get("code"))
                final_validation_warnings = []
                result_path = run_dir / "result" / "result.json" if run_dir else None
                if run_dir:
                    await run_projection_service.write_terminal_projection(
                        run_dir=run_dir,
                        request_id=request_id or f"run:{run_id}",
                        run_id=run_id,
                        status=RunStatus.CANCELED,
                        request_record=request_record,
                        current_attempt=attempt_number,
                        effective_session_timeout_sec=(
                            interactive_profile.session_timeout_sec if interactive_profile is not None else None
                        ),
                        error=canceled_error,
                        warnings=[],
                        terminal_result={
                            "data": None,
                            "artifacts": [],
                            "repair_level": "none",
                            "validation_warnings": [],
                            "error": canceled_error,
                        },
                        run_store_backend=run_store,
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
                        engine_name=engine_name,
                    )
                log_event(
                    logger,
                    event="run.lifecycle.failed",
                    phase="run_lifecycle",
                    outcome="error",
                    level=logging.WARNING,
                    request_id=request_id,
                    run_id=run_id,
                    attempt=attempt_number,
                    engine=engine_name,
                    error_code=final_error_code,
                    error_type="RunCanceled",
                )
            except (AttributeError, RuntimeError, OSError, TypeError, ValueError, LookupError) as e:
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
                result_path = run_dir / "result" / "result.json" if run_dir else None
                if run_dir:
                    await run_projection_service.write_terminal_projection(
                        run_dir=run_dir,
                        request_id=request_id or f"run:{run_id}",
                        run_id=run_id,
                        status=RunStatus.FAILED,
                        request_record=request_record,
                        current_attempt=attempt_number,
                        effective_session_timeout_sec=(
                            interactive_profile.session_timeout_sec if interactive_profile is not None else None
                        ),
                        error=normalized_error,
                        warnings=[],
                        terminal_result={
                            "data": None,
                            "artifacts": [],
                            "repair_level": "none",
                            "validation_warnings": [],
                            "error": normalized_error,
                        },
                        run_store_backend=run_store,
                    )
                await run_store.update_run_status(
                    run_id,
                    RunStatus.FAILED,
                    str(result_path) if result_path is not None else None,
                )
                if run_dir:
                    self._append_orchestrator_event(
                        run_dir=run_dir,
                        attempt_number=attempt_number,
                        category="error",
                        type_name=OrchestratorEventType.ERROR_RUN_FAILED.value,
                        data={"message": normalized_error_message or "unknown"},
                        engine_name=engine_name,
                    )
                log_event(
                    logger,
                    event="run.lifecycle.failed",
                    phase="run_lifecycle",
                    outcome="error",
                    level=logging.ERROR,
                    request_id=request_id,
                    run_id=run_id,
                    attempt=attempt_number,
                    engine=engine_name,
                    error_code=final_error_code,
                    error_type=type(e).__name__,
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
                            auth_detection=auth_detection_result.as_dict(),
                            auth_session=auth_session_meta,
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
                return RunJobOutcome(
                    run_id=run_id,
                    final_status=final_status,
                    error_code=final_error_code,
                    error_message=normalized_error_message,
                    warnings=list(final_validation_warnings),
                )
        finally:
            if run_log_mirror_stack is not None:
                run_log_mirror_stack.close()
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()
                log_event(
                    logger,
                    event="run.lifecycle.slot_released",
                    phase="run_lifecycle",
                    outcome="ok",
                    request_id=request_id if "request_id" in locals() else None,
                    run_id=run_id,
                    attempt=attempt_number if "attempt_number" in locals() else None,
                    engine=engine_name,
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
