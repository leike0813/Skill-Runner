from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from typing import cast

from server.models import (
    AdapterTurnOutcome,
    ExecutionMode,
    InteractiveErrorCode,
    OrchestratorEventType,
    RunStatus,
)
from server.runtime.auth_detection.signal import (
    auth_detection_result_from_auth_signal,
    is_high_confidence_auth_signal,
)
from server.runtime.auth_detection.types import AuthDetectionResult
from server.runtime.adapter.types import RuntimeAuthSignal
from server.runtime.protocol.factories import make_diagnostic_warning_payload
from server.runtime.protocol.parse_utils import extract_fenced_or_plain_json
from server.services.engine_management.model_registry import model_registry
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)

from .run_attempt_execution_service import RunAttemptExecutionResult
from .run_attempt_preparation_service import RunAttemptContext


@dataclass
class RunAttemptOutcomeInputs:
    context: RunAttemptContext
    execution: RunAttemptExecutionResult
    run_id: str
    request_id: str | None
    request_record: dict[str, Any] | None
    options: dict[str, Any]
    skill_id: str
    run_store_backend: Any
    run_output_convergence_service: Any
    auth_orchestration_service: Any
    audit_service: Any
    schema_validator_backend: Any
    append_orchestrator_event: Callable[..., None]
    update_status: Callable[..., Awaitable[None] | None]
    resolve_provider_id: Callable[..., str | None]
    provider_unresolved_detail: Callable[..., str]
    summarize_terminal_error_message: Callable[[Any], str | None]
    resolve_hard_timeout_seconds: Callable[[dict[str, Any]], int]
    live_runtime_emitter_factory: Callable[..., Any]
    collect_run_artifacts: Callable[..., list[str]]
    resolve_output_artifact_paths: Callable[..., Any]
    interaction_service: RunInteractionLifecycleService


_STRICT_FENCED_JSON_RE = re.compile(
    r"^```(?:json)?\s*(\{[\s\S]*\})\s*```$",
    re.IGNORECASE,
)


def parse_runtime_stream_for_auth_detection(
    *,
    adapter: Any | None,
    raw_stdout: str,
    raw_stderr: str,
) -> dict[str, Any] | None:
    if adapter is None or not hasattr(adapter, "parse_runtime_stream"):
        return None
    try:
        parsed = adapter.parse_runtime_stream(
            stdout_raw=raw_stdout.encode("utf-8", errors="replace"),
            stderr_raw=raw_stderr.encode("utf-8", errors="replace"),
            pty_raw=b"",
        )
    except (OSError, RuntimeError, TypeError, ValueError, LookupError):
        return {
            "parser": "auth_detection_fallback",
            "confidence": 0.0,
            "session_id": None,
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": ["AUTH_DETECTION_PARSE_FAILED"],
            "structured_types": [],
        }
    return parsed if isinstance(parsed, dict) else None


def extract_interactive_assistant_json_candidate(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    fenced_match = _STRICT_FENCED_JSON_RE.fullmatch(stripped)
    if fenced_match is not None:
        try:
            parsed = json.loads(fenced_match.group(1))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def materialize_turn_result_payload(turn_result: Any | None) -> dict[str, Any] | None:
    if turn_result is None:
        return None
    outcome = getattr(turn_result, "outcome", None)
    if outcome == AdapterTurnOutcome.FINAL:
        final_data = getattr(turn_result, "final_data", None)
        return dict(final_data) if isinstance(final_data, dict) else None
    if outcome == AdapterTurnOutcome.ASK_USER:
        interaction = getattr(turn_result, "interaction", None)
        if interaction is None:
            return None
        interaction_payload = interaction.model_dump(mode="json")
        return {
            "outcome": AdapterTurnOutcome.ASK_USER.value,
            "action": AdapterTurnOutcome.ASK_USER.value,
            "ask_user": interaction_payload,
            "interaction": interaction_payload,
        }
    return None


def resolve_structured_output_candidate(
    *,
    result: Any,
    runtime_parse_result: dict[str, Any] | None,
    execution_mode: str = "auto",
) -> dict[str, Any] | None:
    payload = materialize_turn_result_payload(getattr(result, "turn_result", None))
    if isinstance(payload, dict):
        outcome = getattr(getattr(result, "turn_result", None), "outcome", None)
        source = "turn_result_final"
        if outcome == AdapterTurnOutcome.ASK_USER:
            source = "turn_result_ask_user"
        elif outcome == AdapterTurnOutcome.ERROR:
            source = "turn_result_error"
        return {"payload": payload, "source": source}
    if not isinstance(runtime_parse_result, dict):
        return None
    assistant_messages = runtime_parse_result.get("assistant_messages")
    if not isinstance(assistant_messages, list):
        return None
    for item in reversed(assistant_messages):
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        parsed = (
            extract_interactive_assistant_json_candidate(text)
            if execution_mode == ExecutionMode.INTERACTIVE.value
            else extract_fenced_or_plain_json(text)
        )
        if isinstance(parsed, dict):
            return {"payload": parsed, "source": "assistant_message_json"}
    return None


def extract_semantic_turn_failed_message(runtime_parse_result: dict[str, Any] | None) -> str | None:
    if not isinstance(runtime_parse_result, dict):
        return None
    turn_failure_data = runtime_parse_result.get("turn_failure_data")
    if isinstance(turn_failure_data, dict):
        message_obj = turn_failure_data.get("message")
        if isinstance(message_obj, str) and message_obj.strip():
            return message_obj.strip()
    turn_markers = runtime_parse_result.get("turn_markers")
    if isinstance(turn_markers, list):
        for marker in reversed(turn_markers):
            if not isinstance(marker, dict):
                continue
            if str(marker.get("marker") or "") != "failed":
                continue
            data_obj = marker.get("data")
            if not isinstance(data_obj, dict):
                continue
            message_obj = data_obj.get("message")
            if isinstance(message_obj, str) and message_obj.strip():
                return message_obj.strip()
    return None


def extract_waiting_auth_reason_message(runtime_parse_result: dict[str, Any] | None) -> str | None:
    semantic_message = extract_semantic_turn_failed_message(runtime_parse_result)
    if isinstance(semantic_message, str) and semantic_message.strip():
        return semantic_message.strip()
    if not isinstance(runtime_parse_result, dict):
        return None
    diagnostic_events = runtime_parse_result.get("diagnostic_events")
    if not isinstance(diagnostic_events, list):
        return None
    preferred_pattern_kinds = (
        "engine_auth_hint",
        "engine_rate_limit_hint",
        "engine_error_row",
        "engine_error_item",
    )
    for pattern_kind in preferred_pattern_kinds:
        for diagnostic in diagnostic_events:
            if not isinstance(diagnostic, dict):
                continue
            if str(diagnostic.get("pattern_kind") or "") != pattern_kind:
                continue
            message_obj = diagnostic.get("message")
            if isinstance(message_obj, str) and message_obj.strip():
                return message_obj.strip()
    return None


@dataclass
class RunAttemptResolvedOutcome:
    final_status: RunStatus
    normalized_error: dict[str, Any] | None
    warnings: list[str]
    output_data: dict[str, Any]
    artifacts: list[str]
    repair_level: str
    pending_interaction: dict[str, Any] | None
    pending_auth: dict[str, Any] | None
    pending_auth_method_selection: dict[str, Any] | None
    auth_session_meta: dict[str, Any] | None
    turn_payload_for_completion: dict[str, Any]
    process_exit_code: int | None
    process_failure_reason: str | None
    process_raw_stdout: str
    process_raw_stderr: str
    auth_detection_result: AuthDetectionResult
    auth_signal_snapshot: dict[str, Any] | None
    runtime_parse_result: dict[str, Any] | None
    terminal_error_summary: str | None
    final_error_code: str | None
    effective_session_timeout_sec: int | None
    auto_resume_requested: bool = False


class RunAttemptOutcomeService:
    async def resolve(
        self,
        *,
        inputs: RunAttemptOutcomeInputs,
    ) -> RunAttemptResolvedOutcome:
        context = inputs.context
        execution = inputs.execution
        result = execution.engine_result
        engine_name = context.request.engine_name
        attempt_number = context.attempt_number
        run_dir = context.run_dir
        request_id = inputs.request_id
        request_record = inputs.request_record
        options = inputs.options
        run_id = inputs.run_id
        skill = context.skill

        process_exit_code = execution.process_exit_code
        process_failure_reason = execution.process_failure_reason
        process_raw_stdout = execution.process_raw_stdout
        process_raw_stderr = execution.process_raw_stderr
        runtime_execution_warnings = list(execution.runtime_execution_warnings)
        runtime_option_warning_payloads = options.get("__runtime_option_warnings")
        if isinstance(runtime_option_warning_payloads, list):
            for warning_payload in runtime_option_warning_payloads:
                if isinstance(warning_payload, dict):
                    runtime_execution_warnings.append(dict(warning_payload))

        runtime_parse_result = parse_runtime_stream_for_auth_detection(
            adapter=context.adapter,
            raw_stdout=process_raw_stdout,
            raw_stderr=process_raw_stderr,
        )
        auth_signal_snapshot = cast(RuntimeAuthSignal | None, execution.auth_signal_snapshot)
        auth_detection_result = auth_detection_result_from_auth_signal(
            engine=engine_name,
            auth_signal=auth_signal_snapshot,
        )
        auth_detection_high = is_high_confidence_auth_signal(auth_signal_snapshot)
        if process_failure_reason == "AUTH_REQUIRED" and not auth_detection_high:
            process_failure_reason = None

        warnings: list[str] = []
        seen_runtime_warning_codes: set[str] = set()
        output_data: dict[str, Any] = {}
        schema_output_errors: list[str] = []
        terminal_validation_errors: list[str] = []
        pending_interaction: dict[str, Any] | None = None
        pending_interaction_candidate: dict[str, Any] | None = None
        pending_auth_method_selection: dict[str, Any] | None = None
        pending_auth: dict[str, Any] | None = None
        repair_level = getattr(result, "repair_level", None) or "none"
        has_structured_output = False
        auth_session_meta: dict[str, Any] | None = None
        turn_payload_for_completion: dict[str, Any] = {}

        def _append_validation_warning(code: str, *, detail: str | None = None) -> None:
            if code not in warnings:
                warnings.append(code)
            if code in seen_runtime_warning_codes:
                return
            seen_runtime_warning_codes.add(code)
            inputs.append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="diagnostic",
                type_name=OrchestratorEventType.DIAGNOSTIC_WARNING.value,
                data=make_diagnostic_warning_payload(
                    code=code,
                    detail=detail,
                ),
                engine_name=engine_name,
            )

        for warning in runtime_execution_warnings:
            if not isinstance(warning, dict):
                continue
            code_obj = warning.get("code")
            if not isinstance(code_obj, str) or not code_obj.strip():
                continue
            warning_code = code_obj.strip()
            warning_detail_obj = warning.get("detail")
            warning_detail = (
                warning_detail_obj.strip()
                if isinstance(warning_detail_obj, str) and warning_detail_obj.strip()
                else None
            )
            _append_validation_warning(warning_code, detail=warning_detail)

        convergence = await inputs.run_output_convergence_service.converge(
            adapter=context.adapter,
            skill=skill,
            input_data=context.input_data,
            run_dir=run_dir,
            request_id=request_id,
            run_store_backend=inputs.run_store_backend,
            run_id=run_id,
            engine_name=engine_name,
            execution_mode=context.execution_mode,
            attempt_number=attempt_number,
            options=context.run_options,
            initial_result=result,
            initial_runtime_parse_result=runtime_parse_result,
            auth_detection_result=auth_detection_result,
            auth_detection_high=auth_detection_high,
            resolve_structured_output_candidate=resolve_structured_output_candidate,
            strip_done_marker_for_output_validation=inputs.interaction_service.strip_done_marker_for_output_validation,
            extract_pending_interaction=inputs.interaction_service.extract_pending_interaction,
            append_orchestrator_event=inputs.append_orchestrator_event,
            append_output_repair_record=inputs.audit_service.append_output_repair_record,
            live_runtime_emitter_factory=inputs.live_runtime_emitter_factory,
        )
        result = convergence.engine_result or result
        if isinstance(convergence.runtime_parse_result, dict):
            runtime_parse_result = convergence.runtime_parse_result
        if convergence.process_exit_code is not None:
            process_exit_code = convergence.process_exit_code
        if convergence.process_failure_reason is not None:
            process_failure_reason = convergence.process_failure_reason
        process_raw_stdout = getattr(result, "raw_stdout", "") or process_raw_stdout
        process_raw_stderr = getattr(result, "raw_stderr", "") or process_raw_stderr
        repair_level = convergence.repair_level or repair_level
        output_data = dict(convergence.output_data)
        has_structured_output = convergence.has_structured_output
        done_signal_found = convergence.done_signal_found
        schema_output_errors = list(convergence.schema_output_errors)
        pending_interaction_candidate = convergence.pending_interaction_candidate
        turn_payload_for_completion = dict(convergence.turn_payload_for_completion)
        for convergence_warning in convergence.validation_warnings:
            _append_validation_warning(convergence_warning)
        if (
            not schema_output_errors
            and has_structured_output
            and convergence.convergence_state == "not_needed"
            and repair_level == "deterministic_generic"
        ):
            _append_validation_warning("OUTPUT_REPAIRED_GENERIC")

        done_marker_found_in_stream = inputs.audit_service.contains_done_marker_in_stream(
            adapter=context.adapter,
            raw_stdout=process_raw_stdout,
            raw_stderr=process_raw_stderr,
        )
        legacy_pending_interaction = inputs.interaction_service.build_default_pending_interaction(
            fallback_interaction_id=attempt_number,
        )

        artifacts = inputs.collect_run_artifacts(run_dir)
        artifact_errors: list[str] = []
        if done_signal_found or (has_structured_output and pending_interaction_candidate is None):
            resolution_result = inputs.resolve_output_artifact_paths(
                skill=skill,
                run_dir=run_dir,
                output_data=output_data,
            )
            output_data = resolution_result.output_data
            artifacts = resolution_result.artifacts
            if isinstance(turn_payload_for_completion, dict) and turn_payload_for_completion:
                turn_payload_for_completion = dict(output_data)
            for warning_code in resolution_result.warnings:
                _append_validation_warning(warning_code)
            schema_output_errors = inputs.schema_validator_backend.validate_output(skill, output_data)
            if resolution_result.missing_required_fields:
                artifact_errors.append(
                    "Missing required artifacts: "
                    + ", ".join(resolution_result.missing_required_fields)
                )

        waiting_auth_reason_message = extract_waiting_auth_reason_message(runtime_parse_result)

        if auth_detection_high and context.session_capable and request_id:
            canonical_provider_id = inputs.resolve_provider_id(
                engine_name=engine_name,
                options=options,
                request_record=request_record,
            )
            created_pending_auth = await inputs.auth_orchestration_service.create_pending_auth(
                run_id=run_id,
                run_dir=run_dir,
                request_id=request_id,
                skill_id=inputs.skill_id,
                engine_name=engine_name,
                options=options,
                attempt_number=attempt_number,
                auth_detection=auth_detection_result,
                canonical_provider_id=canonical_provider_id,
                last_error=waiting_auth_reason_message,
                run_store_backend=inputs.run_store_backend,
                append_orchestrator_event=inputs.append_orchestrator_event,
                update_status=inputs.update_status,
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
                if model_registry.is_multi_provider_engine(engine_name) and canonical_provider_id is None:
                    warning_code = (
                        "OPENCODE_PROVIDER_UNRESOLVED_FROM_MODEL"
                        if engine_name.strip().lower() == "opencode"
                        else "PROVIDER_ID_UNRESOLVED"
                    )
                    _append_validation_warning(
                        warning_code,
                        detail=inputs.provider_unresolved_detail(
                            engine_name=engine_name,
                            options=options,
                            request_record=request_record,
                        ),
                    )
                forced_failure_reason = "AUTH_REQUIRED"
        elif auth_detection_high:
            forced_failure_reason = "AUTH_REQUIRED"
        elif process_failure_reason in {
            "AUTH_REQUIRED",
            "TIMEOUT",
            InteractiveErrorCode.SESSION_RESUME_FAILED.value,
        }:
            forced_failure_reason = process_failure_reason
        else:
            forced_failure_reason = None

        if (
            pending_auth is None
            and pending_auth_method_selection is None
            and context.custom_provider_model is not None
            and request_id
            and context.session_capable
            and (forced_failure_reason is not None or getattr(result, "exit_code", 0) != 0)
        ):
            pending_auth = (
                await inputs.auth_orchestration_service.create_custom_provider_pending_auth(
                    request_id=request_id,
                    run_id=run_id,
                    run_dir=run_dir,
                    engine_name=engine_name,
                    requested_model=context.custom_provider_model,
                    source_attempt=attempt_number,
                    last_error=(
                        waiting_auth_reason_message
                        or "Authentication is required to continue."
                    ),
                    run_store_backend=inputs.run_store_backend,
                    append_orchestrator_event=inputs.append_orchestrator_event,
                )
            ).model_dump(mode="json")
            forced_failure_reason = None

        normalized_status = "success"
        auto_resume_requested = False
        if pending_auth is not None or pending_auth_method_selection is not None:
            normalized_status = RunStatus.WAITING_AUTH.value
        elif forced_failure_reason or getattr(result, "exit_code", 0) != 0:
            normalized_status = "failed"
        elif context.is_interactive:
            final_branch_resolved = bool(done_signal_found)
            pending_branch_resolved = (
                not final_branch_resolved
                and pending_interaction_candidate is not None
            )
            soft_completion = (
                (not final_branch_resolved)
                and (not pending_branch_resolved)
                and has_structured_output
                and not schema_output_errors
            )
            if final_branch_resolved:
                terminal_validation_errors = [*schema_output_errors, *artifact_errors]
                if terminal_validation_errors:
                    normalized_status = "failed"
            elif pending_branch_resolved:
                if context.can_persist_waiting_user:
                    normalized_status = RunStatus.WAITING_USER.value
                    pending_interaction = pending_interaction_candidate
                elif context.interactive_auto_reply and request_id and run_id:
                    normalized_status = RunStatus.QUEUED.value
                    pending_interaction = dict(pending_interaction_candidate)
                    pending_interaction.setdefault("source_attempt", attempt_number)
                    auto_resume_requested = True
                else:
                    forced_failure_reason = "NON_SESSION_INTERACTIVE_REPLY_UNSUPPORTED"
                    normalized_status = "failed"
            elif soft_completion:
                terminal_validation_errors = [*artifact_errors]
                if terminal_validation_errors:
                    normalized_status = "failed"
                else:
                    _append_validation_warning("INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER")
                    if inputs.schema_validator_backend.is_output_schema_too_permissive(skill):
                        _append_validation_warning(
                            "INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE"
                        )
            elif has_structured_output and schema_output_errors:
                _append_validation_warning("INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID")
                if done_marker_found_in_stream:
                    normalized_status = "failed"
                else:
                    max_attempt = skill.max_attempt
                    if max_attempt is not None and attempt_number >= max_attempt:
                        forced_failure_reason = (
                            InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value
                        )
                        normalized_status = "failed"
                    elif context.can_persist_waiting_user:
                        normalized_status = RunStatus.WAITING_USER.value
                        pending_interaction = pending_interaction_candidate or legacy_pending_interaction
                    else:
                        forced_failure_reason = "NON_SESSION_INTERACTIVE_REPLY_UNSUPPORTED"
                        normalized_status = "failed"
            else:
                max_attempt = skill.max_attempt
                if max_attempt is not None and attempt_number >= max_attempt:
                    forced_failure_reason = (
                        InteractiveErrorCode.INTERACTIVE_MAX_ATTEMPT_EXCEEDED.value
                    )
                    normalized_status = "failed"
                elif context.can_persist_waiting_user:
                    normalized_status = RunStatus.WAITING_USER.value
                    pending_interaction = pending_interaction_candidate or legacy_pending_interaction
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
            and context.is_interactive
            and request_id
            and context.interactive_profile
        ):
            wait_status = await inputs.interaction_service.persist_waiting_interaction(
                run_store_backend=inputs.run_store_backend,
                append_internal_schema_warning=inputs.audit_service.append_internal_schema_warning,
                append_orchestrator_event=inputs.audit_service.append_orchestrator_event,
                run_id=run_id,
                run_dir=run_dir,
                request_id=request_id,
                attempt_number=attempt_number,
                profile=context.interactive_profile,
                interactive_auto_reply=context.interactive_auto_reply,
                pending_interaction=pending_interaction,
            )
            if wait_status is not None:
                forced_failure_reason = wait_status
                normalized_status = "failed"
                pending_interaction = None

        has_output_error = bool(terminal_validation_errors)
        normalized_error: dict[str, Any] | None = None
        if normalized_status in {RunStatus.WAITING_USER.value, RunStatus.WAITING_AUTH.value, RunStatus.QUEUED.value}:
            normalized_error = None
        elif normalized_status != "success":
            error_code: str | None = None
            semantic_turn_failed_message = extract_semantic_turn_failed_message(runtime_parse_result)
            if forced_failure_reason == "AUTH_REQUIRED":
                error_code = "AUTH_REQUIRED"
                error_message = "AUTH_REQUIRED: engine authentication is required or expired"
            elif forced_failure_reason == "TIMEOUT":
                error_code = "TIMEOUT"
                effective_timeout = inputs.resolve_hard_timeout_seconds(options)
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
            elif isinstance(semantic_turn_failed_message, str) and semantic_turn_failed_message:
                error_message = semantic_turn_failed_message
            elif has_output_error:
                error_message = "; ".join(terminal_validation_errors)
            else:
                error_message = f"Exit code {getattr(result, 'exit_code', process_exit_code)}"
            normalized_error = {
                "code": error_code,
                "message": error_message,
                "stderr": getattr(result, "raw_stderr", "") or process_raw_stderr,
            }

        if normalized_status == "success":
            final_status = RunStatus.SUCCEEDED
        elif normalized_status == RunStatus.WAITING_USER.value:
            final_status = RunStatus.WAITING_USER
        elif normalized_status == RunStatus.WAITING_AUTH.value:
            final_status = RunStatus.WAITING_AUTH
        elif normalized_status == RunStatus.QUEUED.value:
            final_status = RunStatus.QUEUED
        else:
            final_status = RunStatus.FAILED

        final_error_code = (
            str(normalized_error.get("code"))
            if isinstance(normalized_error, dict) and normalized_error.get("code")
            else None
        )
        terminal_error_summary = inputs.summarize_terminal_error_message(
            normalized_error.get("message") if isinstance(normalized_error, dict) else None
        )
        effective_session_timeout_sec = (
            context.interactive_profile.session_timeout_sec
            if context.interactive_profile is not None
            else None
        )

        return RunAttemptResolvedOutcome(
            final_status=final_status,
            normalized_error=normalized_error,
            warnings=list(warnings),
            output_data=dict(output_data),
            artifacts=list(artifacts),
            repair_level=repair_level,
            pending_interaction=dict(pending_interaction) if isinstance(pending_interaction, dict) else None,
            pending_auth=dict(pending_auth) if isinstance(pending_auth, dict) else None,
            pending_auth_method_selection=(
                dict(pending_auth_method_selection)
                if isinstance(pending_auth_method_selection, dict)
                else None
            ),
            auth_session_meta=dict(auth_session_meta) if isinstance(auth_session_meta, dict) else None,
            turn_payload_for_completion=dict(turn_payload_for_completion),
            process_exit_code=process_exit_code,
            process_failure_reason=process_failure_reason,
            process_raw_stdout=process_raw_stdout,
            process_raw_stderr=process_raw_stderr,
            auth_detection_result=auth_detection_result,
            auth_signal_snapshot=(
                dict(auth_signal_snapshot) if isinstance(auth_signal_snapshot, dict) else None
            ),
            runtime_parse_result=(
                dict(runtime_parse_result) if isinstance(runtime_parse_result, dict) else None
            ),
            terminal_error_summary=terminal_error_summary,
            final_error_code=final_error_code,
            effective_session_timeout_sec=effective_session_timeout_sec,
            auto_resume_requested=auto_resume_requested,
        )
