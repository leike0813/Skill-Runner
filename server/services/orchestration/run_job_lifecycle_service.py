from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from server.models import (
    DispatchPhase,
    EngineSessionHandle,
    EngineSessionHandleType,
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
from server.runtime.session.statechart import timeout_requires_auto_decision
from server.services.orchestration.run_execution_core import resolve_conversation_mode
from server.services.orchestration.run_audit_contract_service import run_audit_contract_service
from server.services.orchestration.run_artifact_path_autofix import (
    collect_run_artifacts,
    resolve_output_artifact_paths,
)
from server.services.orchestration.run_folder_git_initializer import run_folder_git_initializer
from server.services.engine_management.engine_custom_provider_service import (
    engine_custom_provider_service,
)
from server.services.engine_management.model_registry import model_registry
from server.services.orchestration.run_service_log_mirror import RunServiceLogMirrorSession
from server.services.orchestration.run_projection_service import run_projection_service
from server.services.orchestration.run_output_schema_service import run_output_schema_service
from server.services.orchestration.run_output_convergence_service import (
    run_output_convergence_service,
)
from server.services.orchestration.run_skill_materialization_service import run_folder_bootstrapper
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionResult,
)
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptOutcomeInputs,
    RunAttemptResolvedOutcome,
)
from server.services.orchestration.run_attempt_preparation_service import (
    RunAttemptContext,
    resolve_interactive_auto_reply,
    resolve_attempt_number,
)
from server.services.orchestration.run_attempt_projection_finalizer import (
    RunAttemptFinalizeInput,
)
from server.services.platform.async_compat import maybe_await
from server.services.platform.schema_validator import schema_validator
from server.services.skill.skill_asset_resolver import resolve_schema_asset
from server.services.skill.skill_registry import skill_registry

logger = logging.getLogger(__name__)

_TERMINAL_ERROR_SUMMARY_MAX_CHARS = 512


def _normalize_provider_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _provider_from_prefixed_model(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if "/" not in normalized:
        return None
    provider, _rest = normalized.split("/", 1)
    return _normalize_provider_id(provider)


def _iter_request_option_candidates(
    *,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
    key: str,
) -> tuple[Any, ...]:
    request_payload = request_record if isinstance(request_record, dict) else {}
    engine_options = request_payload.get("engine_options")
    effective_runtime_options = request_payload.get("effective_runtime_options")
    runtime_options = request_payload.get("runtime_options")
    return (
        engine_options.get(key) if isinstance(engine_options, dict) else None,
        options.get(key),
        effective_runtime_options.get(key) if isinstance(effective_runtime_options, dict) else None,
        runtime_options.get(key) if isinstance(runtime_options, dict) else None,
    )


def _resolve_provider_id(
    *,
    engine_name: str,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str | None:
    normalized_engine = engine_name.strip().lower()
    requested_model = _resolve_requested_model(options=options, request_record=request_record)
    explicit_provider = None
    for candidate in _iter_request_option_candidates(
        options=options,
        request_record=request_record,
        key="provider_id",
    ):
        explicit_provider = _normalize_provider_id(candidate)
        if explicit_provider is not None:
            break
    if not model_registry.is_multi_provider_engine(normalized_engine):
        return None
    try:
        normalized = model_registry.normalize_model_selection(
            normalized_engine,
            model=requested_model,
            provider_id=explicit_provider,
        )
        return normalized.provider_id
    except ValueError:
        return explicit_provider or _provider_from_prefixed_model(requested_model)


def _resolve_requested_model(
    *,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str | None:
    for candidate in _iter_request_option_candidates(
        options=options,
        request_record=request_record,
        key="model",
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _resolve_claude_custom_model(
    *,
    engine_name: str,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str | None:
    if engine_name.strip().lower() != "claude":
        return None
    provider_id = _resolve_provider_id(
        engine_name=engine_name,
        options=options,
        request_record=request_record,
    )
    model = _resolve_requested_model(options=options, request_record=request_record)
    if not provider_id or not isinstance(model, str) or not model.strip():
        return None
    if provider_id == "anthropic":
        return None
    return f"{provider_id}/{model.strip()}"


def _provider_unresolved_detail(
    *,
    engine_name: str,
    options: Dict[str, Any],
    request_record: Dict[str, Any] | None,
) -> str:
    normalized_engine = engine_name.strip().lower()
    for candidate in _iter_request_option_candidates(
        options=options,
        request_record=request_record,
        key="provider_id",
    ):
        if isinstance(candidate, str) and candidate.strip():
            return (
                f"{normalized_engine} provider could not be resolved from "
                f"engine_options.provider_id={candidate.strip()!r}"
            )
    raw_model = None
    for candidate in _iter_request_option_candidates(
        options=options,
        request_record=request_record,
        key="model",
    ):
        if isinstance(candidate, str) and candidate.strip():
            raw_model = candidate.strip()
            break
    if raw_model is None:
        return (
            f"{normalized_engine} provider could not be resolved because "
            "engine_options.provider_id is missing"
        )
    return (
        f"{normalized_engine} provider could not be resolved from engine_options.model="
        f"{raw_model!r}"
    )


def _summarize_terminal_error_message(message: Any) -> str | None:
    if not isinstance(message, str):
        return None
    normalized = " ".join(message.replace("\r", "\n").split())
    if not normalized:
        return None
    if len(normalized) > _TERMINAL_ERROR_SUMMARY_MAX_CHARS:
        return normalized[: _TERMINAL_ERROR_SUMMARY_MAX_CHARS - 3] + "..."
    return normalized


async def _persist_run_handle_immediate(
    *,
    run_store_backend: Any,
    request_id: str | None,
    engine_name: str,
    attempt_number: int,
    handle_id: str,
) -> dict[str, Any]:
    normalized_handle = handle_id.strip()
    if not normalized_handle:
        return {"status": "skipped"}
    if not isinstance(request_id, str) or not request_id.strip():
        return {"status": "skipped"}

    existing = await maybe_await(run_store_backend.get_engine_session_handle(request_id))
    existing_handle_value = (
        str(existing.get("handle_value")).strip()
        if isinstance(existing, dict) and isinstance(existing.get("handle_value"), str)
        else None
    )
    if isinstance(existing_handle_value, str) and existing_handle_value == normalized_handle:
        return {"status": "unchanged"}

    handle = EngineSessionHandle(
        engine=engine_name,
        handle_type=EngineSessionHandleType.SESSION_ID,
        handle_value=normalized_handle,
        created_at_turn=max(1, int(attempt_number)),
    )
    await maybe_await(
        run_store_backend.set_engine_session_handle(
            request_id,
            handle.model_dump(mode="json"),
        )
    )
    if isinstance(existing_handle_value, str) and existing_handle_value:
        logger.warning(
            "run_handle_changed request_id=%s attempt=%s engine=%s previous=%s current=%s",
            request_id,
            attempt_number,
            engine_name,
            existing_handle_value,
            normalized_handle,
        )
        return {
            "status": "changed",
            "previous_handle_id": existing_handle_value,
            "current_handle_id": normalized_handle,
        }
    logger.info(
        "run_handle_persisted request_id=%s attempt=%s engine=%s handle_id=%s",
        request_id,
        attempt_number,
        engine_name,
        normalized_handle,
    )
    return {"status": "stored"}


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


async def _noop_run_handle_consumer(_handle_id: str) -> dict[str, Any]:
    return {"status": "skipped"}


def _default_execution_result() -> RunAttemptExecutionResult:
    return RunAttemptExecutionResult(
        engine_result=None,
        process_exit_code=None,
        process_failure_reason=None,
        process_raw_stdout="",
        process_raw_stderr="",
        runtime_execution_warnings=[],
        adapter_stream_parser=None,
        auth_signal_snapshot=None,
        run_handle_consumer=_noop_run_handle_consumer,
        live_runtime_emitter_factory=lambda: None,
    )


def _build_fallback_attempt_context(
    *,
    request: RunJobRequest,
    run_dir: Path,
    request_record: dict[str, Any] | None,
    request_id: str | None,
    execution_mode: str,
    conversation_mode: str,
    session_capable: bool,
    is_interactive: bool,
    interactive_auto_reply: bool,
    can_wait_for_user: bool,
    can_persist_waiting_user: bool,
    interactive_profile: EngineInteractiveProfile | None,
    attempt_number: int,
    adapter: Any | None,
    run_options: dict[str, Any] | None,
) -> RunAttemptContext:
    return RunAttemptContext(
        request=request,
        run_dir=run_dir,
        request_record=request_record if isinstance(request_record, dict) else None,
        request_id=request_id if isinstance(request_id, str) else None,
        execution_mode=execution_mode,
        conversation_mode=conversation_mode,
        session_capable=session_capable,
        is_interactive=is_interactive,
        interactive_auto_reply=interactive_auto_reply,
        can_wait_for_user=can_wait_for_user,
        can_persist_waiting_user=can_persist_waiting_user,
        interactive_profile=interactive_profile,
        attempt_number=attempt_number,
        skill=cast(Any, request.skill_override or object()),
        adapter=adapter,
        input_data={"input": {}, "parameter": {}},
        run_options=dict(run_options or {}),
        custom_provider_model=None,
    )


def _build_terminal_outcome(
    *,
    final_status: RunStatus,
    normalized_error: dict[str, Any] | None,
    warnings: list[str],
    final_error_code: str | None,
    terminal_error_summary: str | None,
    effective_session_timeout_sec: int | None,
    auth_detection_result: AuthDetectionResult,
    auth_session_meta: dict[str, Any] | None,
    process_exit_code: int | None,
    process_failure_reason: str | None,
    process_raw_stdout: str,
    process_raw_stderr: str,
) -> RunAttemptResolvedOutcome:
    return RunAttemptResolvedOutcome(
        final_status=final_status,
        normalized_error=normalized_error,
        warnings=list(warnings),
        output_data={},
        artifacts=[],
        repair_level="none",
        pending_interaction=None,
        pending_auth=None,
        pending_auth_method_selection=None,
        auth_session_meta=(
            dict(auth_session_meta) if isinstance(auth_session_meta, dict) else None
        ),
        turn_payload_for_completion={},
        process_exit_code=process_exit_code,
        process_failure_reason=process_failure_reason,
        process_raw_stdout=process_raw_stdout,
        process_raw_stderr=process_raw_stderr,
        auth_detection_result=auth_detection_result,
        auth_signal_snapshot=None,
        runtime_parse_result=None,
        terminal_error_summary=terminal_error_summary,
        final_error_code=final_error_code,
        effective_session_timeout_sec=effective_session_timeout_sec,
        auto_resume_requested=False,
    )


def _build_finalize_input(
    *,
    request: RunJobRequest,
    context: RunAttemptContext | None,
    execution: RunAttemptExecutionResult,
    outcome: RunAttemptResolvedOutcome,
    run_dir: Path,
    request_record: dict[str, Any] | None,
    request_id: str | None,
    execution_mode: str,
    conversation_mode: str,
    session_capable: bool,
    is_interactive: bool,
    interactive_auto_reply: bool,
    can_wait_for_user: bool,
    can_persist_waiting_user: bool,
    interactive_profile: EngineInteractiveProfile | None,
    attempt_number: int,
    adapter: Any | None,
    run_options: dict[str, Any] | None,
    run_id: str,
    cache_key: str | None,
    attempt_started_at: datetime,
    fs_before_snapshot: dict[str, dict[str, Any]],
    run_store_backend: Any,
    run_projection_backend: Any,
    audit_service: Any,
    build_run_bundle: Any,
    options: dict[str, Any],
) -> RunAttemptFinalizeInput:
    resolved_context = context or _build_fallback_attempt_context(
        request=request,
        run_dir=run_dir,
        request_record=request_record,
        request_id=request_id,
        execution_mode=execution_mode,
        conversation_mode=conversation_mode,
        session_capable=session_capable,
        is_interactive=is_interactive,
        interactive_auto_reply=interactive_auto_reply,
        can_wait_for_user=can_wait_for_user,
        can_persist_waiting_user=can_persist_waiting_user,
        interactive_profile=interactive_profile,
        attempt_number=attempt_number,
        adapter=adapter,
        run_options=run_options,
    )
    return RunAttemptFinalizeInput(
        context=resolved_context,
        execution=execution,
        outcome=outcome,
        request_record=request_record,
        run_id=run_id,
        request_id=request_id,
        cache_key=cache_key,
        attempt_started_at=attempt_started_at,
        fs_before_snapshot=fs_before_snapshot,
        run_store_backend=run_store_backend,
        run_projection_service=run_projection_backend,
        audit_service=audit_service,
        build_run_bundle=build_run_bundle,
        summarize_terminal_error_message=_summarize_terminal_error_message,
        execution_mode=execution_mode,
        options=options,
        adapter=adapter,
    )


class _RunJobLifecyclePipeline:
    @staticmethod
    async def run_job(
        orchestrator: Any,
        request: RunJobRequest,
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
        run_id = request.run_id
        skill_id = request.skill_id
        engine_name = request.engine_name
        options = request.options
        cache_key = request.cache_key
        slot_acquired = False
        release_slot_on_exit = True
        run_dir: Path | None = None
        run_log_mirror_stack: contextlib.ExitStack | None = None
        run_store = orchestrator._run_store_backend()
        workspace_manager = orchestrator._workspace_backend()
        concurrency_manager = orchestrator._concurrency_backend()
        run_folder_trust_manager = orchestrator._trust_manager_backend()
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
            interactive_auto_reply = resolve_interactive_auto_reply(
                options=options,
                request_record=request_record or {},
            )
            can_wait_for_user = is_interactive and session_capable
            interactive_profile: Optional[EngineInteractiveProfile] = None
            if can_wait_for_user and request_id:
                interactive_profile = await orchestrator._resolve_interactive_profile(
                    request_id=request_id,
                    engine_name=engine_name,
                    options=options,
                )
            can_persist_waiting_user = can_wait_for_user
            attempt_override_obj = options.get("__attempt_number_override")
            if isinstance(attempt_override_obj, int) and attempt_override_obj > 0:
                attempt_number = attempt_override_obj
            else:
                attempt_number = await resolve_attempt_number(
                    run_store_backend=run_store,
                    request_id=request_id,
                    is_interactive=is_interactive,
                )
            resume_ticket_id = (
                str(options.get("__resume_ticket_id"))
                if isinstance(options.get("__resume_ticket_id"), str)
                and str(options.get("__resume_ticket_id")).strip()
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
            fs_before_snapshot = orchestrator.snapshot_service.capture_filesystem_snapshot(run_dir)
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
                canceled_error = orchestrator._build_canceled_error()
                result_path = orchestrator._write_canceled_result(run_dir, canceled_error)
                orchestrator._update_status(
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
            terminal_error_summary: Optional[str] = None
            adapter: Any | None = None
            context: RunAttemptContext | None = None
            execution: RunAttemptExecutionResult = _default_execution_result()
            current_outcome: RunAttemptResolvedOutcome | None = None

            # 1. Update status to RUNNING
            orchestrator._update_status(
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
            orchestrator.audit_service.append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="lifecycle",
                type_name=OrchestratorEventType.LIFECYCLE_RUN_STARTED.value,
                data={"status": RunStatus.RUNNING.value},
                engine_name=engine_name,
            )
            orchestrator._update_latest_run_id(run_id)

            try:
                preparation = await orchestrator.run_attempt_preparation_service.prepare(
                    orchestrator=orchestrator,
                    request=request,
                    run_dir=run_dir,
                    request_record=request_record,
                    request_id=request_id,
                    execution_mode=execution_mode,
                    conversation_mode=conversation_mode,
                    session_capable=session_capable,
                    is_interactive=is_interactive,
                    interactive_auto_reply=interactive_auto_reply,
                    can_wait_for_user=can_wait_for_user,
                    can_persist_waiting_user=can_persist_waiting_user,
                    interactive_profile=interactive_profile,
                    attempt_number=attempt_number,
                    resolve_custom_provider_model=_resolve_claude_custom_model,
                    run_store_backend=run_store,
                    interaction_service=orchestrator.interaction_service,
                    audit_service=orchestrator.audit_service,
                    resolve_attempt_number=lambda **kwargs: resolve_attempt_number(
                        run_store_backend=run_store,
                        **kwargs,
                    ),
                    build_reply_prompt=orchestrator._build_reply_prompt,
                )
                context = preparation
                skill = preparation.skill
                adapter = preparation.adapter
                input_data = preparation.input_data
                run_options = dict(preparation.run_options)

                if await run_store.is_cancel_requested(run_id):
                    raise RunCanceled()

                custom_provider_model = preparation.custom_provider_model
                if (
                    custom_provider_model is not None
                    and request_id
                    and session_capable
                    and engine_custom_provider_service.resolve_model(engine_name, custom_provider_model) is None
                ):
                    bootstrap_pending_auth = (
                        await orchestrator.auth_orchestration_service.create_custom_provider_pending_auth(
                        request_id=request_id,
                        run_id=run_id,
                        run_dir=run_dir,
                        engine_name=engine_name,
                        requested_model=custom_provider_model,
                        source_attempt=attempt_number,
                        run_store_backend=run_store,
                        append_orchestrator_event=orchestrator.audit_service.append_orchestrator_event,
                    )
                    ).model_dump(mode="json")
                    final_status = RunStatus.WAITING_AUTH
                    current_outcome = RunAttemptResolvedOutcome(
                        final_status=RunStatus.WAITING_AUTH,
                        normalized_error=None,
                        warnings=[],
                        output_data={},
                        artifacts=[],
                        repair_level="none",
                        pending_interaction=None,
                        pending_auth=dict(bootstrap_pending_auth),
                        pending_auth_method_selection=None,
                        auth_session_meta=None,
                        turn_payload_for_completion={},
                        process_exit_code=process_exit_code,
                        process_failure_reason=process_failure_reason,
                        process_raw_stdout=process_raw_stdout,
                        process_raw_stderr=process_raw_stderr,
                        auth_detection_result=auth_detection_result,
                        auth_signal_snapshot=None,
                        runtime_parse_result=runtime_parse_result,
                        terminal_error_summary=None,
                        final_error_code=None,
                        effective_session_timeout_sec=(
                            interactive_profile.session_timeout_sec
                            if interactive_profile is not None
                            else None
                        ),
                        auto_resume_requested=False,
                    )
                    logger.info(
                        "run_attempt_waiting_auth_custom_provider_bootstrap run_id=%s request_id=%s attempt=%s model=%s",
                        run_id,
                        request_id,
                        attempt_number,
                        custom_provider_model,
                    )
                    return RunJobOutcome(run_id=run_id, final_status=RunStatus.WAITING_AUTH)

                async def _consume_run_handle(handle_id: str) -> dict[str, Any]:
                    return await _persist_run_handle_immediate(
                        run_store_backend=run_store,
                        request_id=request_id,
                        engine_name=engine_name,
                        attempt_number=attempt_number,
                        handle_id=handle_id,
                    )
                execution = await orchestrator.run_attempt_execution_service.execute(
                    context=preparation,
                    trust_manager_backend=run_folder_trust_manager,
                    run_handle_consumer=_consume_run_handle,
                )
                result = execution.engine_result
                process_exit_code = execution.process_exit_code
                process_failure_reason = execution.process_failure_reason
                logger.info(
                    "run_attempt_execute_end run_id=%s request_id=%s attempt=%s exit_code=%s failure_reason=%s",
                    run_id,
                    request_id,
                    attempt_number,
                    process_exit_code,
                    process_failure_reason,
                )
                process_raw_stdout = execution.process_raw_stdout
                process_raw_stderr = execution.process_raw_stderr
                if await run_store.is_cancel_requested(run_id):
                    raise RunCanceled()
                outcome: RunAttemptResolvedOutcome = await orchestrator.run_attempt_outcome_service.resolve(
                    inputs=RunAttemptOutcomeInputs(
                        context=preparation,
                        execution=execution,
                        run_id=run_id,
                        request_id=request_id,
                        request_record=request_record,
                        options=options,
                        skill_id=skill_id,
                        run_store_backend=run_store,
                        run_output_convergence_service=run_output_convergence_service,
                        auth_orchestration_service=orchestrator.auth_orchestration_service,
                        audit_service=orchestrator.audit_service,
                        schema_validator_backend=schema_validator,
                        append_orchestrator_event=orchestrator.audit_service.append_orchestrator_event,
                        update_status=orchestrator._update_status,
                        resolve_provider_id=_resolve_provider_id,
                        provider_unresolved_detail=_provider_unresolved_detail,
                        summarize_terminal_error_message=_summarize_terminal_error_message,
                        resolve_hard_timeout_seconds=orchestrator._resolve_hard_timeout_seconds,
                        live_runtime_emitter_factory=execution.live_runtime_emitter_factory,
                        collect_run_artifacts=collect_run_artifacts,
                        resolve_output_artifact_paths=resolve_output_artifact_paths,
                        interaction_service=orchestrator.interaction_service,
                    )
                )
                final_status = outcome.final_status
                current_outcome = outcome
                normalized_error = outcome.normalized_error
                normalized_error_message = (
                    str(normalized_error.get("message"))
                    if isinstance(normalized_error, dict) and normalized_error.get("message") is not None
                    else None
                )
                final_validation_warnings = list(outcome.warnings)
                final_error_code = outcome.final_error_code
                terminal_error_summary = outcome.terminal_error_summary
                output_data = dict(outcome.output_data)
                artifacts = list(outcome.artifacts)
                repair_level = outcome.repair_level
                pending_interaction = (
                    dict(outcome.pending_interaction)
                    if isinstance(outcome.pending_interaction, dict)
                    else None
                )
                pending_auth = (
                    dict(outcome.pending_auth) if isinstance(outcome.pending_auth, dict) else None
                )
                pending_auth_method_selection = (
                    dict(outcome.pending_auth_method_selection)
                    if isinstance(outcome.pending_auth_method_selection, dict)
                    else None
                )
                auth_session_meta = (
                    dict(outcome.auth_session_meta)
                    if isinstance(outcome.auth_session_meta, dict)
                    else None
                )
                turn_payload_for_completion = dict(outcome.turn_payload_for_completion)
                process_exit_code = outcome.process_exit_code
                process_failure_reason = outcome.process_failure_reason
                process_raw_stdout = outcome.process_raw_stdout
                process_raw_stderr = outcome.process_raw_stderr
                auth_detection_result = outcome.auth_detection_result
                runtime_parse_result = outcome.runtime_parse_result

                if (
                    final_status == RunStatus.QUEUED
                    and outcome.auto_resume_requested
                    and pending_interaction is not None
                    and request_id
                ):
                    await maybe_await(
                        run_store.set_pending_interaction(
                            request_id,
                            pending_interaction,
                        )
                    )
                    await maybe_await(
                        run_store.append_interaction_history(
                            request_id=request_id,
                            interaction_id=int(pending_interaction["interaction_id"]),
                            event_type="ask_user",
                            payload=pending_interaction,
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
                        orchestrator._resume_with_auto_decision(
                            request_record=request_record or {},
                            run_id=run_id,
                            request_id=request_id,
                            pending_interaction=pending_interaction,
                        )
                    )
                    return RunJobOutcome(run_id=run_id, final_status=RunStatus.QUEUED)

                if (
                    final_status == RunStatus.WAITING_USER
                    and interactive_profile is not None
                    and request_id
                    and pending_interaction
                ):
                    if timeout_requires_auto_decision(interactive_auto_reply):
                        delay_sec = max(1, int(interactive_profile.session_timeout_sec))
                        asyncio.create_task(
                            orchestrator._auto_decide_after_timeout(
                                request_id=request_id,
                                run_id=run_id,
                                delay_sec=delay_sec,
                            )
                        )
                await orchestrator.run_attempt_projection_finalizer.finalize(
                    inputs=RunAttemptFinalizeInput(
                        context=preparation,
                        execution=execution,
                        outcome=outcome,
                        request_record=request_record,
                        run_id=run_id,
                        request_id=request_id,
                        cache_key=cache_key,
                        attempt_started_at=attempt_started_at,
                        fs_before_snapshot=fs_before_snapshot,
                        run_store_backend=run_store,
                        run_projection_service=run_projection_service,
                        audit_service=orchestrator.audit_service,
                        build_run_bundle=orchestrator.build_run_bundle,
                        summarize_terminal_error_message=_summarize_terminal_error_message,
                        execution_mode=execution_mode,
                        options=options,
                        adapter=adapter,
                    )
                )

            except RunCanceled:
                final_status = RunStatus.CANCELED
                canceled_error = orchestrator._build_canceled_error()
                normalized_error_message = canceled_error["message"]
                final_error_code = str(canceled_error.get("code"))
                final_validation_warnings = []
                current_outcome = _build_terminal_outcome(
                    final_status=RunStatus.CANCELED,
                    normalized_error=canceled_error,
                    warnings=[],
                    final_error_code=final_error_code,
                    terminal_error_summary=_summarize_terminal_error_message(
                        canceled_error.get("message")
                    ),
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                    auth_detection_result=auth_detection_result,
                    auth_session_meta=auth_session_meta,
                    process_exit_code=process_exit_code,
                    process_failure_reason=process_failure_reason,
                    process_raw_stdout=process_raw_stdout,
                    process_raw_stderr=process_raw_stderr,
                )
                if run_dir:
                    await orchestrator.run_attempt_projection_finalizer.finalize(
                        inputs=_build_finalize_input(
                            request=request,
                            context=context,
                            execution=execution,
                            outcome=current_outcome,
                            run_dir=run_dir,
                            request_record=request_record,
                            request_id=request_id,
                            execution_mode=execution_mode,
                            conversation_mode=conversation_mode,
                            session_capable=session_capable,
                            is_interactive=is_interactive,
                            interactive_auto_reply=interactive_auto_reply,
                            can_wait_for_user=can_wait_for_user,
                            can_persist_waiting_user=can_persist_waiting_user,
                            interactive_profile=interactive_profile,
                            attempt_number=attempt_number,
                            adapter=adapter,
                            run_options=context.run_options if context is not None else options,
                            run_id=run_id,
                            cache_key=cache_key,
                            attempt_started_at=attempt_started_at,
                            fs_before_snapshot=fs_before_snapshot,
                            run_store_backend=run_store,
                            run_projection_backend=run_projection_service,
                            audit_service=orchestrator.audit_service,
                            build_run_bundle=orchestrator.build_run_bundle,
                            options=options,
                        ),
                        terminal_event_type_name=OrchestratorEventType.LIFECYCLE_RUN_CANCELED.value,
                        failure_error_type="RunCanceled",
                    )
            except (AttributeError, RuntimeError, OSError, TypeError, ValueError, LookupError) as e:
                # Orchestration boundary: normalize unknown runtime exceptions into terminal error payload.
                logger.exception("Job failed")
                final_status = RunStatus.FAILED
                normalized_error = orchestrator._error_from_exception(e)
                normalized_error_message = str(normalized_error.get("message", str(e)))
                final_error_code = (
                    str(normalized_error.get("code"))
                    if isinstance(normalized_error, dict) and normalized_error.get("code")
                    else None
                )
                final_validation_warnings = []
                current_outcome = _build_terminal_outcome(
                    final_status=RunStatus.FAILED,
                    normalized_error=normalized_error,
                    warnings=[],
                    final_error_code=final_error_code,
                    terminal_error_summary=_summarize_terminal_error_message(
                        normalized_error_message
                    ),
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                    auth_detection_result=auth_detection_result,
                    auth_session_meta=auth_session_meta,
                    process_exit_code=process_exit_code,
                    process_failure_reason=process_failure_reason,
                    process_raw_stdout=process_raw_stdout,
                    process_raw_stderr=process_raw_stderr,
                )
                if run_dir:
                    await orchestrator.run_attempt_projection_finalizer.finalize(
                        inputs=_build_finalize_input(
                            request=request,
                            context=context,
                            execution=execution,
                            outcome=current_outcome,
                            run_dir=run_dir,
                            request_record=request_record,
                            request_id=request_id,
                            execution_mode=execution_mode,
                            conversation_mode=conversation_mode,
                            session_capable=session_capable,
                            is_interactive=is_interactive,
                            interactive_auto_reply=interactive_auto_reply,
                            can_wait_for_user=can_wait_for_user,
                            can_persist_waiting_user=can_persist_waiting_user,
                            interactive_profile=interactive_profile,
                            attempt_number=attempt_number,
                            adapter=adapter,
                            run_options=context.run_options if context is not None else options,
                            run_id=run_id,
                            cache_key=cache_key,
                            attempt_started_at=attempt_started_at,
                            fs_before_snapshot=fs_before_snapshot,
                            run_store_backend=run_store,
                            run_projection_backend=run_projection_service,
                            audit_service=orchestrator.audit_service,
                            build_run_bundle=orchestrator.build_run_bundle,
                            options=options,
                        ),
                        emit_error_run_failed_event=True,
                        failure_error_type=type(e).__name__,
                    )
            finally:
                if run_dir is not None and current_outcome is not None:
                    orchestrator.run_attempt_audit_finalizer.finalize(
                        inputs=_build_finalize_input(
                            request=request,
                            context=context,
                            execution=execution,
                            outcome=current_outcome,
                            run_dir=run_dir,
                            request_record=request_record,
                            request_id=request_id,
                            execution_mode=execution_mode,
                            conversation_mode=conversation_mode,
                            session_capable=session_capable,
                            is_interactive=is_interactive,
                            interactive_auto_reply=interactive_auto_reply,
                            can_wait_for_user=can_wait_for_user,
                            can_persist_waiting_user=can_persist_waiting_user,
                            interactive_profile=interactive_profile,
                            attempt_number=attempt_number,
                            adapter=adapter,
                            run_options=context.run_options if context is not None else options,
                            run_id=run_id,
                            cache_key=cache_key,
                            attempt_started_at=attempt_started_at,
                            fs_before_snapshot=fs_before_snapshot,
                            run_store_backend=run_store,
                            run_projection_backend=run_projection_service,
                            audit_service=orchestrator.audit_service,
                            build_run_bundle=orchestrator.build_run_bundle,
                            options=options,
                        ),
                        finished_at=datetime.utcnow(),
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
            request=request,
        )
