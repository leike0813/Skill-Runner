from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from server.models import OrchestratorEventType, PendingOwner, RunStatus
from server.runtime.logging.structured_trace import log_event

from .run_attempt_execution_service import RunAttemptExecutionResult
from .run_attempt_outcome_service import RunAttemptResolvedOutcome
from .run_attempt_preparation_service import RunAttemptContext

logger = logging.getLogger(__name__)


@dataclass
class RunAttemptFinalizeInput:
    context: RunAttemptContext
    execution: RunAttemptExecutionResult
    outcome: RunAttemptResolvedOutcome
    request_record: dict[str, Any] | None
    run_id: str
    request_id: str | None
    cache_key: str | None
    attempt_started_at: datetime
    fs_before_snapshot: dict[str, dict[str, Any]]
    run_store_backend: Any
    run_projection_service: Any
    audit_service: Any
    build_run_bundle: Callable[[Path, bool], str]
    summarize_terminal_error_message: Callable[[Any], str | None]
    execution_mode: str
    options: dict[str, Any]
    adapter: Any | None = None


@dataclass
class RunAttemptProjectionResult:
    result_path: Path | None
    projection_request_id: str
    final_status: RunStatus
    bundle_written: bool
    cache_recorded: bool


class RunAttemptProjectionFinalizer:
    async def finalize(
        self,
        *,
        inputs: RunAttemptFinalizeInput,
        terminal_event_type_name: str = OrchestratorEventType.LIFECYCLE_RUN_TERMINAL.value,
        emit_error_run_failed_event: bool = False,
        failure_error_type: str | None = None,
    ) -> RunAttemptProjectionResult:
        context = inputs.context
        outcome = inputs.outcome
        run_dir = context.run_dir
        engine_name = context.request.engine_name
        attempt_number = context.attempt_number
        final_status = outcome.final_status
        warnings = list(outcome.warnings)
        projection_request_id = inputs.request_id or f"run:{inputs.run_id}"
        effective_session_timeout_sec = outcome.effective_session_timeout_sec
        result_path: Path | None = None
        bundle_written = False
        cache_recorded = False

        if final_status == RunStatus.WAITING_USER and outcome.pending_interaction is not None:
            pending_interaction = dict(outcome.pending_interaction)
            logger.info(
                "run_attempt_waiting_user run_id=%s request_id=%s attempt=%s interaction_id=%s",
                inputs.run_id,
                projection_request_id,
                attempt_number,
                pending_interaction.get("interaction_id"),
            )
            await inputs.run_projection_service.write_non_terminal_projection(
                run_dir=run_dir,
                request_id=projection_request_id,
                run_id=inputs.run_id,
                status=RunStatus.WAITING_USER,
                request_record=inputs.request_record,
                current_attempt=attempt_number,
                pending_owner=PendingOwner.WAITING_USER,
                pending_interaction=pending_interaction,
                source_attempt=attempt_number,
                effective_session_timeout_sec=effective_session_timeout_sec,
                warnings=warnings,
                error=None,
                run_store_backend=inputs.run_store_backend,
            )
            await inputs.run_store_backend.update_run_status(inputs.run_id, final_status)
            log_event(
                logger,
                event="run.lifecycle.waiting_user",
                phase="run_lifecycle",
                outcome="ok",
                request_id=inputs.request_id,
                run_id=inputs.run_id,
                attempt=attempt_number,
                engine=engine_name,
                interaction_id=pending_interaction.get("interaction_id"),
            )
            return RunAttemptProjectionResult(
                result_path=None,
                projection_request_id=projection_request_id,
                final_status=final_status,
                bundle_written=False,
                cache_recorded=False,
            )

        if final_status == RunStatus.WAITING_AUTH:
            logger.info(
                "run_attempt_waiting_auth run_id=%s request_id=%s attempt=%s",
                inputs.run_id,
                projection_request_id,
                attempt_number,
            )
            pending_owner = None
            if outcome.pending_auth_method_selection is not None:
                pending_owner = PendingOwner.WAITING_AUTH_METHOD_SELECTION
            elif outcome.pending_auth is not None:
                pending_owner = PendingOwner.WAITING_AUTH_CHALLENGE
            await inputs.run_projection_service.write_non_terminal_projection(
                run_dir=run_dir,
                request_id=projection_request_id,
                run_id=inputs.run_id,
                status=RunStatus.WAITING_AUTH,
                request_record=inputs.request_record,
                current_attempt=attempt_number,
                pending_owner=pending_owner,
                pending_auth_method_selection=outcome.pending_auth_method_selection,
                pending_auth=outcome.pending_auth,
                source_attempt=attempt_number,
                effective_session_timeout_sec=effective_session_timeout_sec,
                warnings=warnings,
                error=None,
                run_store_backend=inputs.run_store_backend,
            )
            await inputs.run_store_backend.update_run_status(inputs.run_id, final_status)
            log_event(
                logger,
                event="run.lifecycle.waiting_auth",
                phase="run_lifecycle",
                outcome="ok",
                request_id=inputs.request_id,
                run_id=inputs.run_id,
                attempt=attempt_number,
                engine=engine_name,
            )
            return RunAttemptProjectionResult(
                result_path=None,
                projection_request_id=projection_request_id,
                final_status=final_status,
                bundle_written=False,
                cache_recorded=False,
            )

        logger.info(
            "run_attempt_terminal run_id=%s request_id=%s attempt=%s status=%s",
            inputs.run_id,
            projection_request_id,
            attempt_number,
            final_status.value,
        )
        await inputs.run_projection_service.write_terminal_projection(
            run_dir=run_dir,
            request_id=projection_request_id,
            run_id=inputs.run_id,
            status=final_status,
            request_record=inputs.request_record,
            current_attempt=attempt_number,
            effective_session_timeout_sec=effective_session_timeout_sec,
            warnings=warnings,
            error=outcome.normalized_error,
            terminal_result={
                "data": outcome.output_data if final_status == RunStatus.SUCCEEDED else None,
                "success_source": outcome.success_source,
                "artifacts": list(outcome.artifacts),
                "repair_level": outcome.repair_level,
                "validation_warnings": warnings,
                "error": outcome.normalized_error,
            },
            run_store_backend=inputs.run_store_backend,
        )
        result_path = run_dir / "result" / "result.json"
        await inputs.run_store_backend.update_run_status(
            inputs.run_id,
            final_status,
            str(result_path),
        )

        if final_status == RunStatus.SUCCEEDED:
            log_event(
                logger,
                event="run.lifecycle.succeeded",
                phase="run_lifecycle",
                outcome="ok",
                level=logging.INFO,
                request_id=inputs.request_id,
                run_id=inputs.run_id,
                attempt=attempt_number,
                engine=engine_name,
                error_code=outcome.final_error_code,
            )
        else:
            log_event(
                logger,
                event="run.lifecycle.failed",
                phase="run_lifecycle",
                outcome="error",
                level=logging.WARNING if final_status == RunStatus.CANCELED else logging.ERROR,
                request_id=inputs.request_id,
                run_id=inputs.run_id,
                attempt=attempt_number,
                engine=engine_name,
                error_code=outcome.final_error_code,
                error_type=failure_error_type,
            )

        if final_status == RunStatus.SUCCEEDED:
            inputs.build_run_bundle(run_dir, False)
            inputs.build_run_bundle(run_dir, True)
            bundle_written = True

        if final_status == RunStatus.CANCELED:
            inputs.audit_service.append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="lifecycle",
                type_name=terminal_event_type_name,
                data={"status": RunStatus.CANCELED.value},
                engine_name=engine_name,
            )
        elif final_status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
            terminal_payload: dict[str, Any] = {"status": final_status.value}
            if isinstance(outcome.success_source, str) and outcome.success_source:
                terminal_payload["completion_source"] = outcome.success_source
            if final_status == RunStatus.FAILED:
                if isinstance(outcome.final_error_code, str) and outcome.final_error_code:
                    terminal_payload["code"] = outcome.final_error_code
                if isinstance(outcome.terminal_error_summary, str) and outcome.terminal_error_summary:
                    terminal_payload["message"] = outcome.terminal_error_summary
            inputs.audit_service.append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="lifecycle",
                type_name=terminal_event_type_name,
                data=terminal_payload,
                engine_name=engine_name,
            )

        if emit_error_run_failed_event:
            inputs.audit_service.append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=attempt_number,
                category="error",
                type_name=OrchestratorEventType.ERROR_RUN_FAILED.value,
                data={
                    "message": inputs.summarize_terminal_error_message(
                        outcome.normalized_error.get("message")
                        if isinstance(outcome.normalized_error, dict)
                        else None
                    )
                    or "unknown",
                    "code": outcome.final_error_code or "ORCHESTRATOR_ERROR",
                },
                engine_name=engine_name,
            )

        if inputs.cache_key and final_status == RunStatus.SUCCEEDED:
            skill_source = (
                str((inputs.request_record or {}).get("skill_source") or "installed")
                if isinstance(inputs.request_record, dict)
                else "installed"
            )
            if skill_source == "temp_upload":
                await inputs.run_store_backend.record_temp_cache_entry(inputs.cache_key, inputs.run_id)
            else:
                await inputs.run_store_backend.record_cache_entry(inputs.cache_key, inputs.run_id)
            cache_recorded = True

        return RunAttemptProjectionResult(
            result_path=result_path,
            projection_request_id=projection_request_id,
            final_status=final_status,
            bundle_written=bundle_written,
            cache_recorded=cache_recorded,
        )
