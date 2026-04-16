from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from fastapi import BackgroundTasks, HTTPException  # type: ignore[import-not-found]
from pydantic import ValidationError

from server.models import (
    AskUserHintPayload,
    AuthChallengeKind,
    AuthMethod,
    AuthMethodSelection,
    PendingOwner,
    AuthSessionPhase,
    AuthSessionStatusResponse,
    AuthSubmission,
    AuthSubmissionKind,
    InteractiveErrorCode,
    InteractionReplyResponse,
    InteractionOption,
    OrchestratorEventType,
    PendingAuth,
    PendingAuthMethodSelection,
    ResumeCause,
    RunStatus,
)
from server.runtime.auth_detection.types import AuthDetectionResult
from server.runtime.logging.structured_trace import log_event
from server.services.engine_management.engine_auth_strategy_service import engine_auth_strategy_service
from server.services.engine_management.engine_auth_flow_manager import engine_auth_flow_manager
from server.services.engine_management.engine_custom_provider_service import (
    engine_custom_provider_service,
)
from server.services.engine_management.model_registry import model_registry
from server.services.engine_management.auth_import_service import (
    AuthImportError,
    AuthImportValidationError,
    auth_import_service,
)
from server.services.engine_management.engine_interaction_gate import EngineInteractionBusyError
from server.services.orchestration.run_store import run_store
from server.services.orchestration.run_projection_service import run_projection_service
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.platform.async_compat import maybe_await
from server.services.platform.concurrency_manager import concurrency_manager

logger = logging.getLogger(__name__)

_CONVERSATION_METHOD_MAP: dict[str, AuthMethod] = {
    "callback": AuthMethod.CALLBACK,
    "device_auth": AuthMethod.DEVICE_AUTH,
    "auth_code_or_url": AuthMethod.AUTH_CODE_OR_URL,
    "import": AuthMethod.IMPORT,
    "api_key": AuthMethod.API_KEY,
    "custom_provider": AuthMethod.CUSTOM_PROVIDER,
}
_HIGH_RISK_SHORT_LABEL = "High risk!"
_HIGH_RISK_NOTICE = (
    "This third-party login path may violate Google policies and could lead to account suspension."
)
_AUTH_SIGNAL_PROVIDER_FALLBACKS: dict[str, dict[str, str]] = {
    "qwen": {
        "qwen_oauth_waiting_authorization": "qwen-oauth",
    }
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | None = None) -> str:
    target = value or _utc_now()
    return target.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timeout_sec_from_snapshot(snapshot: dict[str, Any]) -> int | None:
    created_at = _parse_utc(snapshot.get("created_at"))
    expires_at = _parse_utc(snapshot.get("expires_at"))
    if created_at is None or expires_at is None:
        return None
    delta = int((expires_at - created_at).total_seconds())
    return delta if delta > 0 else None


class RunAuthOrchestrationService:
    def __init__(self) -> None:
        self._callback_dispatch_loop: asyncio.AbstractEventLoop | None = None
        engine_auth_flow_manager.register_completion_listener(
            self._dispatch_engine_callback_completion
        )

    async def create_pending_auth(
        self,
        *,
        run_id: str,
        run_dir: Path,
        request_id: str,
        skill_id: str,
        engine_name: str,
        options: dict[str, Any],
        attempt_number: int,
        auth_detection: AuthDetectionResult,
        canonical_provider_id: str | None = None,
        last_error: str | None = None,
        run_store_backend: Any = run_store,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
    ) -> PendingAuth | PendingAuthMethodSelection | None:
        self._capture_runtime_loop()
        _ = skill_id
        _ = options
        provider_id = self._resolve_effective_provider_id(
            engine_name=engine_name,
            auth_detection=auth_detection,
            canonical_provider_id=canonical_provider_id,
            options=options,
        )
        available_methods = self._available_methods_for(engine_name, provider_id)
        if not available_methods:
            log_event(
                logger,
                event="auth.failed",
                phase="auth_orchestration",
                outcome="error",
                level=logging.WARNING,
                request_id=request_id,
                run_id=run_id,
                attempt=attempt_number,
                engine=engine_name,
                provider_id=provider_id,
                error_code="NO_AVAILABLE_AUTH_METHODS",
            )
            return None
        if len(available_methods) > 1:
            selection = self._build_method_selection(
                engine=engine_name,
                provider_id=provider_id,
                available_methods=available_methods,
                source_attempt=attempt_number,
                last_error=last_error,
            )
            await self._persist_method_selection(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                selection=selection,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
            )
            return selection
        if available_methods[0] == AuthMethod.IMPORT:
            pending_auth = self._build_import_pending_auth(
                request_id=request_id,
                engine=engine_name,
                provider_id=provider_id,
                source_attempt=attempt_number,
                last_error=last_error,
            )
            await self._persist_pending_auth(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                pending_auth=pending_auth,
                snapshot={},
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                event_type=OrchestratorEventType.AUTH_METHOD_SELECTED.value,
            )
            return pending_auth
        try:
            pending_auth = await self._start_pending_auth(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                engine=engine_name,
                provider_id=provider_id,
                auth_method=available_methods[0],
                source_attempt=attempt_number,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
            )
        except EngineInteractionBusyError as exc:
            recovered_pending_auth = await self._recover_active_pending_auth(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                engine=engine_name,
                provider_id=provider_id,
                auth_method=available_methods[0],
                source_attempt=attempt_number,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
            )
            if recovered_pending_auth is not None:
                return recovered_pending_auth
            selection = self._build_method_selection(
                engine=engine_name,
                provider_id=provider_id,
                available_methods=available_methods,
                source_attempt=attempt_number,
                last_error=str(exc),
            )
            await self._persist_method_selection(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                selection=selection,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
                event_type=OrchestratorEventType.AUTH_SESSION_BUSY.value,
            )
            return selection
        except (RuntimeError, OSError, TypeError, ValueError, LookupError) as exc:
            selection = self._build_method_selection(
                engine=engine_name,
                provider_id=provider_id,
                available_methods=available_methods,
                source_attempt=attempt_number,
                last_error=str(exc),
            )
            await self._persist_method_selection(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                selection=selection,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
                event_type=OrchestratorEventType.AUTH_SESSION_BUSY.value,
            )
            return selection
        return self._apply_last_error_to_pending_auth(pending_auth, last_error)

    async def create_custom_provider_pending_auth(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        engine_name: str | None = None,
        engine: str | None = None,
        requested_model: str,
        source_attempt: int,
        last_error: str | None = None,
        run_store_backend: Any = run_store,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None] | None = None,
    ) -> PendingAuth:
        resolved_engine = self._normalize_string(engine_name) or self._normalize_string(engine)
        if resolved_engine is None:
            raise HTTPException(status_code=422, detail="engine is required")
        pending_auth = self._build_custom_provider_pending_auth(
            request_id=request_id,
            engine=resolved_engine,
            requested_model=requested_model,
            source_attempt=source_attempt,
            last_error=last_error,
        )
        snapshot = {
            "session_id": pending_auth.auth_session_id,
            "engine": resolved_engine,
            "provider_id": pending_auth.provider_id,
            "auth_method": AuthMethod.CUSTOM_PROVIDER.value,
            "input_kind": AuthSubmissionKind.CUSTOM_PROVIDER.value,
            "status": "waiting_user",
            "created_at": pending_auth.created_at,
            "expires_at": pending_auth.expires_at,
        }
        await self._persist_pending_auth(
            request_id=request_id,
            run_id=run_id,
            run_dir=run_dir,
            pending_auth=pending_auth,
            snapshot=snapshot,
            run_store_backend=run_store_backend,
            append_orchestrator_event=append_orchestrator_event,
            event_type=OrchestratorEventType.AUTH_CHALLENGE_UPDATED.value,
        )
        _ = update_status
        return pending_auth

    async def select_auth_method(
        self,
        *,
        request_id: str,
        run_id: str,
        selection: AuthMethodSelection,
        background_tasks: BackgroundTasks,
        run_store_backend: Any = run_store,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        resume_run_job: Callable[..., Any],
    ) -> InteractionReplyResponse:
        self._capture_runtime_loop()
        _ = background_tasks
        _ = resume_run_job
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            raise HTTPException(status_code=404, detail="Request not found")
        run_id_obj = request_record.get("run_id")
        resolved_run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else run_id
        run_dir = workspace_manager.get_run_dir(resolved_run_id)
        if run_dir is None:
            raise HTTPException(status_code=404, detail="Run not found")
        existing_pending = await maybe_await(run_store_backend.get_pending_auth(request_id))
        existing_selection = await maybe_await(run_store_backend.get_pending_auth_method_selection(request_id))
        has_pending_challenge = isinstance(existing_pending, dict)
        has_pending_selection = isinstance(existing_selection, dict)
        if not has_pending_challenge and not has_pending_selection:
            raise HTTPException(status_code=409, detail="No pending auth flow")
        if has_pending_challenge and not has_pending_selection:
            raise HTTPException(status_code=409, detail="Auth challenge already active")
        source_attempt = self._resolve_source_attempt(existing_pending, existing_selection)
        provider_id = self._resolve_provider_id(existing_pending, existing_selection)
        available_methods = self._available_methods_for(
            str((existing_pending or existing_selection or {}).get("engine") or request_record.get("engine") or ""),
            provider_id,
        )
        if selection.value not in available_methods:
            log_event(
                logger,
                event="auth.failed",
                phase="auth_orchestration",
                outcome="error",
                level=logging.WARNING,
                request_id=request_id,
                run_id=resolved_run_id,
                attempt=source_attempt,
                selected_method=selection.value,
                available_methods=available_methods,
                error_code="UNSUPPORTED_AUTH_METHOD",
            )
            raise HTTPException(status_code=422, detail="Unsupported auth method")
        engine_name = str((existing_pending or existing_selection or {}).get("engine") or request_record.get("engine") or "")
        if selection.value == AuthMethod.IMPORT:
            pending_auth = self._build_import_pending_auth(
                request_id=request_id,
                engine=engine_name,
                provider_id=provider_id,
                source_attempt=source_attempt,
            )
            await self._persist_pending_auth(
                request_id=request_id,
                run_id=resolved_run_id,
                run_dir=run_dir,
                pending_auth=pending_auth,
                snapshot={},
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                event_type=OrchestratorEventType.AUTH_METHOD_SELECTED.value,
            )
            return InteractionReplyResponse(
                request_id=request_id,
                status=RunStatus.WAITING_AUTH,
                accepted=True,
                mode="auth",
            )
        try:
            pending_auth = await self._start_pending_auth(
                request_id=request_id,
                run_id=resolved_run_id,
                run_dir=run_dir,
                engine=engine_name,
                provider_id=provider_id,
                auth_method=selection.value,
                source_attempt=source_attempt,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
                event_type=OrchestratorEventType.AUTH_METHOD_SELECTED.value,
            )
        except EngineInteractionBusyError as exc:
            selection_payload = self._build_method_selection(
                engine=engine_name,
                provider_id=provider_id,
                available_methods=available_methods,
                source_attempt=source_attempt,
                last_error=str(exc),
            )
            await self._persist_method_selection(
                request_id=request_id,
                run_id=resolved_run_id,
                run_dir=run_dir,
                selection=selection_payload,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
                event_type=OrchestratorEventType.AUTH_SESSION_BUSY.value,
            )
            return InteractionReplyResponse(
                request_id=request_id,
                status=RunStatus.WAITING_AUTH,
                accepted=True,
                mode="auth",
            )
        return InteractionReplyResponse(
            request_id=request_id,
            status=RunStatus.WAITING_AUTH,
            accepted=pending_auth is not None,
            mode="auth",
        )

    async def submit_auth_input(
        self,
        *,
        request_id: str,
        run_id: str,
        request: AuthSubmission,
        auth_session_id: str,
        background_tasks: BackgroundTasks,
        run_store_backend: Any = run_store,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        resume_run_job: Callable[..., Any],
    ) -> InteractionReplyResponse:
        self._capture_runtime_loop()
        pending_payload = await maybe_await(run_store_backend.get_pending_auth(request_id))
        if not isinstance(pending_payload, dict):
            raise HTTPException(status_code=409, detail="No pending auth session")
        current_auth_session_id = pending_payload.get("auth_session_id")
        if current_auth_session_id != auth_session_id:
            raise HTTPException(status_code=409, detail="stale auth session")
        if (
            request.kind == AuthSubmissionKind.CUSTOM_PROVIDER
            and auth_session_id.startswith("provider-config::")
        ):
            request_record = await maybe_await(run_store_backend.get_request(request_id))
            run_dir = workspace_manager.get_run_dir(run_id)
            if run_dir is None:
                raise HTTPException(status_code=404, detail="Run not found")
            source_attempt = self._resolve_source_attempt(pending_payload, None)
            await self._apply_custom_provider_submission(
                request_id=request_id,
                request_record=request_record if isinstance(request_record, dict) else None,
                submission=request.value,
                run_store_backend=run_store_backend,
            )
            resume_ticket_id = await self._complete_waiting_auth_success(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                auth_session_id=auth_session_id,
                source_attempt=source_attempt,
                background_tasks=background_tasks,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                resume_run_job=resume_run_job,
            )
            log_event(
                logger,
                event="auth.completed",
                phase="auth_orchestration",
                outcome="ok",
                request_id=request_id,
                run_id=run_id,
                attempt=source_attempt,
                auth_session_id=auth_session_id,
                resume_ticket_id=resume_ticket_id,
            )
            return InteractionReplyResponse(
                request_id=request_id,
                status=RunStatus.QUEUED,
                accepted=True,
                mode="auth",
            )
        resume_context = await maybe_await(run_store_backend.get_auth_resume_context(request_id))
        runtime_kind = self._map_submission_kind_to_runtime_kind(
            submission=request,
            resume_context=resume_context if isinstance(resume_context, dict) else None,
        )
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            raise HTTPException(status_code=404, detail="Run not found")
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=self._resolve_source_attempt(pending_payload, resume_context),
            category="interaction",
            type_name=OrchestratorEventType.AUTH_INPUT_ACCEPTED.value,
            data=self._build_auth_input_accepted_payload(
                auth_session_id=auth_session_id,
                submission_kind=request.kind,
            ),
        )
        log_event(
            logger,
            event="auth.input.accepted",
            phase="auth_orchestration",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=self._resolve_source_attempt(pending_payload, resume_context),
            auth_session_id=auth_session_id,
            submission_kind=request.kind,
        )
        try:
            snapshot = engine_auth_flow_manager.input_session(auth_session_id, runtime_kind, request.value)
        except KeyError as exc:
            log_event(
                logger,
                event="auth.failed",
                phase="auth_orchestration",
                outcome="error",
                level=logging.WARNING,
                request_id=request_id,
                run_id=run_id,
                auth_session_id=auth_session_id,
                error_code="STALE_AUTH_SESSION",
                error_type=type(exc).__name__,
            )
            raise HTTPException(status_code=409, detail="stale auth session") from exc
        except ValueError as exc:
            reconciled = await self._reconcile_completed_auth_session_if_needed(
                auth_session_id=auth_session_id,
                append_orchestrator_event=append_orchestrator_event,
                update_status=update_status,
                resume_run_job=resume_run_job,
                run_store_backend=run_store_backend,
            )
            if reconciled:
                raise HTTPException(status_code=409, detail="Auth session already completed") from exc
            detail = str(exc).strip() or "Invalid auth input"
            if self._is_stale_auth_input_error(detail):
                log_event(
                    logger,
                    event="auth.failed",
                    phase="auth_orchestration",
                    outcome="error",
                    level=logging.WARNING,
                    request_id=request_id,
                    run_id=run_id,
                    auth_session_id=auth_session_id,
                    error_code="STALE_AUTH_INPUT",
                    error_type=type(exc).__name__,
                )
                raise HTTPException(status_code=409, detail=detail) from exc
            log_event(
                logger,
                event="auth.failed",
                phase="auth_orchestration",
                outcome="error",
                level=logging.WARNING,
                request_id=request_id,
                run_id=run_id,
                auth_session_id=auth_session_id,
                error_code="INVALID_AUTH_INPUT",
                error_type=type(exc).__name__,
            )
            raise HTTPException(status_code=422, detail=detail) from exc
        resolved_auth_method = self._require_auth_method(
            self._resolve_auth_method(pending_payload, resume_context),
            submission_kind=request.kind,
        )
        pending_auth = self._build_pending_auth_from_snapshot(
            snapshot=snapshot,
            auth_method=resolved_auth_method,
            source_attempt=self._resolve_source_attempt(pending_payload, resume_context),
            last_error=self._normalize_string(snapshot.get("error")),
        )
        if self._snapshot_is_terminal_success(snapshot):
            source_attempt = self._resolve_source_attempt(pending_payload, resume_context)
            resume_ticket_id = await self._complete_waiting_auth_success(
                request_id=request_id,
                run_id=run_id,
                run_dir=run_dir,
                auth_session_id=auth_session_id,
                source_attempt=source_attempt,
                background_tasks=background_tasks,
                run_store_backend=run_store_backend,
                append_orchestrator_event=append_orchestrator_event,
                resume_run_job=resume_run_job,
            )
            log_event(
                logger,
                event="auth.completed",
                phase="auth_orchestration",
                outcome="ok",
                request_id=request_id,
                run_id=run_id,
                attempt=source_attempt,
                auth_session_id=auth_session_id,
                resume_ticket_id=resume_ticket_id,
            )
            return InteractionReplyResponse(
                request_id=request_id,
                status=RunStatus.QUEUED,
                accepted=True,
                mode="auth",
            )
        await maybe_await(
            run_store_backend.set_pending_auth(
                request_id,
                pending_auth.model_dump(mode="json"),
                auth_resume_context=self._build_auth_resume_context(
                    snapshot=snapshot,
                    auth_method=pending_auth.auth_method,
                    source_attempt=pending_auth.source_attempt,
                ),
            )
        )
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=pending_auth.source_attempt,
            category="interaction",
            type_name=(
                OrchestratorEventType.AUTH_SESSION_TIMED_OUT.value
                if self._snapshot_timed_out(snapshot)
                else OrchestratorEventType.AUTH_CHALLENGE_UPDATED.value
            ),
            data=self._build_pending_auth_event_payload(pending_auth),
        )
        log_event(
            logger,
            event="auth.challenge.published",
            phase="auth_orchestration",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=pending_auth.source_attempt,
            auth_session_id=pending_auth.auth_session_id,
            challenge_kind=pending_auth.challenge_kind,
        )
        await run_projection_service.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.WAITING_AUTH,
            current_attempt=pending_auth.source_attempt,
            pending_owner=PendingOwner.WAITING_AUTH_CHALLENGE,
            pending_auth=pending_auth.model_dump(mode="json"),
            source_attempt=pending_auth.source_attempt,
            effective_session_timeout_sec=self._positive_int_or_none(pending_auth.timeout_sec),
            run_store_backend=run_store_backend,
        )
        return InteractionReplyResponse(
            request_id=request_id,
            status=RunStatus.WAITING_AUTH,
            accepted=True,
            mode="auth",
        )

    async def submit_auth_import(
        self,
        *,
        request_id: str,
        run_id: str,
        provider_id: str | None,
        files: dict[str, bytes],
        background_tasks: BackgroundTasks,
        run_store_backend: Any = run_store,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        resume_run_job: Callable[..., Any],
    ) -> InteractionReplyResponse:
        self._capture_runtime_loop()
        _ = update_status
        pending_auth_payload = await maybe_await(run_store_backend.get_pending_auth(request_id))
        pending_selection_payload = await maybe_await(
            run_store_backend.get_pending_auth_method_selection(request_id)
        )
        if not isinstance(pending_auth_payload, dict) and not isinstance(pending_selection_payload, dict):
            raise HTTPException(status_code=409, detail="No pending auth flow")
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            raise HTTPException(status_code=404, detail="Request not found")
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            raise HTTPException(status_code=404, detail="Run not found")
        engine = self._normalize_string(request_record.get("engine")) or ""
        pending_provider_id = self._resolve_provider_id(
            pending_auth_payload,
            pending_selection_payload,
        )
        effective_provider_id = self._normalize_provider_id(provider_id) or pending_provider_id
        available_methods = self._available_methods_for(engine, effective_provider_id)
        if AuthMethod.IMPORT not in available_methods:
            raise HTTPException(status_code=422, detail="Import auth method is not available")
        source_attempt = self._resolve_source_attempt(
            pending_auth_payload,
            pending_selection_payload,
        )
        try:
            import_result = auth_import_service.import_auth_files(
                engine=engine,
                provider_id=effective_provider_id,
                files=files,
            )
        except (AuthImportError, AuthImportValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        auth_session_id = (
            self._normalize_string((pending_auth_payload or {}).get("auth_session_id"))
            or f"import::{request_id}::{uuid.uuid4()}"
        )
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=source_attempt,
            category="interaction",
            type_name=OrchestratorEventType.AUTH_INPUT_ACCEPTED.value,
            data=self._build_auth_input_accepted_payload(
                auth_session_id=auth_session_id,
                submission_kind=AuthSubmissionKind.IMPORT_FILES,
            ),
        )
        log_event(
            logger,
            event="auth.input.accepted",
            phase="auth_orchestration",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=source_attempt,
            auth_session_id=auth_session_id,
            submission_kind=AuthSubmissionKind.IMPORT_FILES,
            imported_files=len(import_result.get("imported_files", [])),
        )

        resume_ticket_id = await self._complete_waiting_auth_success(
            request_id=request_id,
            run_id=run_id,
            run_dir=run_dir,
            auth_session_id=auth_session_id,
            source_attempt=source_attempt,
            background_tasks=background_tasks,
            run_store_backend=run_store_backend,
            append_orchestrator_event=append_orchestrator_event,
            resume_run_job=resume_run_job,
        )
        log_event(
            logger,
            event="auth.completed",
            phase="auth_orchestration",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=source_attempt,
            auth_session_id=auth_session_id,
            resume_ticket_id=resume_ticket_id,
            import_mode="file_import",
        )
        return InteractionReplyResponse(
            request_id=request_id,
            status=RunStatus.QUEUED,
            accepted=True,
            mode="auth",
        )

    async def _complete_waiting_auth_success(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        auth_session_id: str,
        source_attempt: int,
        background_tasks: BackgroundTasks,
        run_store_backend: Any,
        append_orchestrator_event: Callable[..., None],
        resume_run_job: Callable[..., Any],
    ) -> str:
        target_attempt = source_attempt + 1
        resume_ticket = await maybe_await(
            run_store_backend.issue_resume_ticket(
                request_id,
                cause=ResumeCause.AUTH_COMPLETED.value,
                source_attempt=source_attempt,
                target_attempt=target_attempt,
                payload={"auth_session_id": auth_session_id},
            )
        )
        ticket_dispatched = await maybe_await(
            run_store_backend.mark_resume_ticket_dispatched(
                request_id,
                str(resume_ticket["ticket_id"]),
            )
        )
        if ticket_dispatched:
            await maybe_await(run_store_backend.clear_pending_auth(request_id))
            await maybe_await(run_store_backend.clear_pending_auth_method_selection(request_id))
            await maybe_await(run_store_backend.clear_auth_resume_context(request_id))
            await run_projection_service.write_non_terminal_projection(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_id,
                status=RunStatus.QUEUED,
                current_attempt=source_attempt,
                pending_owner=None,
                resume_ticket_id=str(resume_ticket["ticket_id"]),
                resume_cause=ResumeCause.AUTH_COMPLETED,
                source_attempt=source_attempt,
                target_attempt=target_attempt,
                run_store_backend=run_store_backend,
            )
            append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=source_attempt,
                category="interaction",
                type_name=OrchestratorEventType.AUTH_SESSION_COMPLETED.value,
                data=self._build_auth_session_completed_payload(
                    auth_session_id=auth_session_id,
                    source_attempt=source_attempt,
                    target_attempt=target_attempt,
                    resume_ticket_id=str(resume_ticket["ticket_id"]),
                    ticket_consumed=True,
                ),
            )
            await self._schedule_resume(
                request_id=request_id,
                background_tasks=background_tasks,
                run_store_backend=run_store_backend,
                resume_run_job=resume_run_job,
                target_attempt=target_attempt,
                resume_ticket_id=str(resume_ticket["ticket_id"]),
                resume_cause=ResumeCause.AUTH_COMPLETED.value,
            )
        return str(resume_ticket["ticket_id"])

    async def get_auth_session_status(
        self,
        *,
        request_id: str,
        append_orchestrator_event: Callable[..., None] | None = None,
        update_status: Callable[..., None] | None = None,
        resume_run_job: Callable[..., Any] | None = None,
        run_store_backend: Any = run_store,
    ) -> AuthSessionStatusResponse:
        self._capture_runtime_loop()
        await self.reconcile_waiting_auth(
            request_id=request_id,
            append_orchestrator_event=append_orchestrator_event,
            update_status=update_status,
            resume_run_job=resume_run_job,
            run_store_backend=run_store_backend,
        )
        payload = await maybe_await(run_store_backend.get_auth_session_status(request_id))
        if not isinstance(payload, dict):
            payload = {}
        waiting_auth = bool(payload.get("waiting_auth"))
        phase_raw = payload.get("phase")
        phase = AuthSessionPhase(phase_raw) if isinstance(phase_raw, str) and phase_raw in {
            AuthSessionPhase.METHOD_SELECTION.value,
            AuthSessionPhase.CHALLENGE_ACTIVE.value,
        } else None
        selected_method = self._enum_or_none(AuthMethod, payload.get("selected_method"))
        challenge_kind = self._enum_or_none(AuthChallengeKind, payload.get("challenge_kind"))
        available_methods = [
            method
            for method in (
                self._enum_or_none(AuthMethod, item)
                for item in payload.get("available_methods", [])
            )
            if method is not None
        ]
        return AuthSessionStatusResponse(
            request_id=request_id,
            waiting_auth=waiting_auth,
            phase=phase,
            timed_out=bool(payload.get("timed_out")),
            available_methods=available_methods,
            selected_method=selected_method,
            auth_session_id=self._normalize_string(payload.get("auth_session_id")),
            challenge_kind=challenge_kind,
            timeout_sec=self._positive_int_or_none(payload.get("timeout_sec")),
            created_at=self._normalize_string(payload.get("created_at")),
            expires_at=self._normalize_string(payload.get("expires_at")),
            server_now=self._normalize_string(payload.get("server_now")) or _utc_iso(),
            last_error=self._normalize_string(payload.get("last_error")),
            source_attempt=self._positive_int_or_none(payload.get("source_attempt")),
            target_attempt=self._positive_int_or_none(payload.get("target_attempt")),
            resume_ticket_id=self._normalize_string(payload.get("resume_ticket_id")),
            ticket_consumed=bool(payload.get("ticket_consumed")),
            pending_owner=self._enum_or_none(PendingOwner, payload.get("pending_owner")),
        )

    async def reconcile_waiting_auth(
        self,
        *,
        request_id: str,
        append_orchestrator_event: Callable[..., None] | None = None,
        update_status: Callable[..., None] | None = None,
        resume_run_job: Callable[..., Any] | None = None,
        run_store_backend: Any = run_store,
    ) -> bool:
        payload = await maybe_await(run_store_backend.get_auth_session_status(request_id))
        if not isinstance(payload, dict) or not bool(payload.get("waiting_auth")):
            return False
        resolved_handlers = self._resolve_runtime_handlers(
            append_orchestrator_event=append_orchestrator_event,
            update_status=update_status,
            resume_run_job=resume_run_job,
        )
        if resolved_handlers is None:
            return False
        resolved_append, resolved_update, resolved_resume = resolved_handlers
        auth_session_id = self._normalize_string(payload.get("auth_session_id"))
        if auth_session_id is None:
            return False
        snapshot: dict[str, Any] | None
        try:
            snapshot = engine_auth_flow_manager.get_session(auth_session_id)
        except KeyError:
            snapshot = None
        if isinstance(snapshot, dict):
            if self._snapshot_is_terminal_success(snapshot):
                await self.handle_callback_completion(
                    snapshot=snapshot,
                    append_orchestrator_event=resolved_append,
                    update_status=resolved_update,
                    resume_run_job=resolved_resume,
                    run_store_backend=run_store_backend,
                )
                return True
            if self._snapshot_timed_out(snapshot):
                await self._fail_waiting_auth_session(
                    request_id=request_id,
                    auth_session_id=auth_session_id,
                    reason="auth session expired before completion",
                    append_orchestrator_event=resolved_append,
                    update_status=resolved_update,
                    run_store_backend=run_store_backend,
                )
                return True
            return False
        if bool(payload.get("timed_out")):
            await self._fail_waiting_auth_session(
                request_id=request_id,
                auth_session_id=auth_session_id,
                reason="auth session state missing after timeout",
                append_orchestrator_event=resolved_append,
                update_status=resolved_update,
                run_store_backend=run_store_backend,
            )
            return True
        return False

    async def handle_callback_completion(
        self,
        *,
        snapshot: dict[str, Any],
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        resume_run_job: Callable[..., Any],
        run_store_backend: Any = run_store,
    ) -> None:
        auth_session_id = self._normalize_string(snapshot.get("session_id"))
        if auth_session_id is None:
            return
        request_id = await maybe_await(run_store_backend.get_request_id_for_auth_session(auth_session_id))
        if not isinstance(request_id, str) or not request_id:
            return
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            return
        run_id = self._normalize_string(request_record.get("run_id"))
        if run_id is None:
            return
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            return
        pending_payload = await maybe_await(run_store_backend.get_pending_auth(request_id))
        resume_context = await maybe_await(run_store_backend.get_auth_resume_context(request_id))
        source_attempt = self._resolve_source_attempt(pending_payload, resume_context)
        if self._snapshot_is_terminal_success(snapshot):
            target_attempt = source_attempt + 1
            resume_ticket = await maybe_await(
                run_store_backend.issue_resume_ticket(
                    request_id,
                    cause=ResumeCause.AUTH_COMPLETED.value,
                    source_attempt=source_attempt,
                    target_attempt=target_attempt,
                    payload={"auth_session_id": auth_session_id},
                )
            )
            ticket_dispatched = await maybe_await(
                run_store_backend.mark_resume_ticket_dispatched(
                    request_id,
                    str(resume_ticket["ticket_id"]),
                )
            )
            if ticket_dispatched:
                await maybe_await(run_store_backend.clear_pending_auth(request_id))
                await maybe_await(run_store_backend.clear_pending_auth_method_selection(request_id))
                await maybe_await(run_store_backend.clear_auth_resume_context(request_id))
                await run_projection_service.write_non_terminal_projection(
                    run_dir=run_dir,
                    request_id=request_id,
                    run_id=run_id,
                    status=RunStatus.QUEUED,
                    current_attempt=source_attempt,
                    pending_owner=None,
                    resume_ticket_id=str(resume_ticket["ticket_id"]),
                    resume_cause=ResumeCause.AUTH_COMPLETED,
                    source_attempt=source_attempt,
                    target_attempt=target_attempt,
                    run_store_backend=run_store_backend,
                )
                append_orchestrator_event(
                    run_dir=run_dir,
                    attempt_number=source_attempt,
                    category="interaction",
                    type_name=OrchestratorEventType.AUTH_SESSION_COMPLETED.value,
                    data=self._build_auth_session_completed_payload(
                        auth_session_id=auth_session_id,
                        source_attempt=source_attempt,
                        target_attempt=target_attempt,
                        resume_ticket_id=str(resume_ticket["ticket_id"]),
                        ticket_consumed=True,
                    ),
                )
                await self._schedule_resume_async(
                    request_id=request_id,
                    run_store_backend=run_store_backend,
                    resume_run_job=resume_run_job,
                    target_attempt=target_attempt,
                    resume_ticket_id=str(resume_ticket["ticket_id"]),
                    resume_cause=ResumeCause.AUTH_COMPLETED.value,
                )
            return
        auth_method = self._require_auth_method(
            self._resolve_auth_method(pending_payload, resume_context),
            submission_kind=None,
        )
        pending_auth = self._build_pending_auth_from_snapshot(
            snapshot=snapshot,
            auth_method=auth_method,
            source_attempt=source_attempt,
            last_error=self._normalize_string(snapshot.get("error")),
        )
        await maybe_await(
            run_store_backend.set_pending_auth(
                request_id,
                pending_auth.model_dump(mode="json"),
                auth_resume_context=self._build_auth_resume_context(
                    snapshot=snapshot,
                    auth_method=pending_auth.auth_method,
                    source_attempt=pending_auth.source_attempt,
                ),
            )
        )
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=source_attempt,
            category="interaction",
            type_name=(
                OrchestratorEventType.AUTH_SESSION_TIMED_OUT.value
                if self._snapshot_timed_out(snapshot)
                else OrchestratorEventType.AUTH_CHALLENGE_UPDATED.value
            ),
            data=self._build_pending_auth_event_payload(pending_auth),
        )
        update_status(run_dir, RunStatus.WAITING_AUTH)
        await maybe_await(run_store_backend.update_run_status(run_id, RunStatus.WAITING_AUTH))

    async def _reconcile_completed_auth_session_if_needed(
        self,
        *,
        auth_session_id: str,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        resume_run_job: Callable[..., Any],
        run_store_backend: Any,
    ) -> bool:
        try:
            snapshot = engine_auth_flow_manager.get_session(auth_session_id)
        except KeyError:
            return False
        if not isinstance(snapshot, dict) or not self._snapshot_is_terminal_success(snapshot):
            return False
        await self.handle_callback_completion(
            snapshot=snapshot,
            append_orchestrator_event=append_orchestrator_event,
            update_status=update_status,
            resume_run_job=resume_run_job,
            run_store_backend=run_store_backend,
        )
        return True

    async def _fail_waiting_auth_session(
        self,
        *,
        request_id: str,
        auth_session_id: str,
        reason: str,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        run_store_backend: Any,
    ) -> None:
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            return
        run_id = self._normalize_string(request_record.get("run_id"))
        if run_id is None:
            return
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            return
        error = {
            "code": InteractiveErrorCode.SESSION_RESUME_FAILED.value,
            "message": f"{InteractiveErrorCode.SESSION_RESUME_FAILED.value}: {reason}",
        }
        pending_auth = await maybe_await(run_store_backend.get_pending_auth(request_id))
        resume_context = await maybe_await(run_store_backend.get_auth_resume_context(request_id))
        source_attempt = self._resolve_source_attempt(pending_auth, resume_context)
        timed_out_payload = dict(pending_auth) if isinstance(pending_auth, dict) else None
        if isinstance(timed_out_payload, dict):
            timed_out_payload["last_error"] = reason
        await maybe_await(run_store_backend.clear_pending_auth(request_id))
        await maybe_await(run_store_backend.clear_pending_auth_method_selection(request_id))
        await maybe_await(run_store_backend.clear_auth_resume_context(request_id))
        update_status(
            run_dir,
            RunStatus.FAILED,
            error=error,
            effective_session_timeout_sec=await maybe_await(
                run_store_backend.get_effective_session_timeout(request_id)
            ),
        )
        await maybe_await(run_store_backend.update_run_status(run_id, RunStatus.FAILED))
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=source_attempt,
            category="interaction",
            type_name=OrchestratorEventType.AUTH_SESSION_TIMED_OUT.value,
            data=self._build_auth_session_timed_out_payload(
                auth_session_id=auth_session_id,
                request_record=request_record,
                source_attempt=source_attempt,
                reason=reason,
                existing_payload=timed_out_payload if isinstance(timed_out_payload, dict) else None,
            ),
        )

    async def _start_pending_auth(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        engine: str,
        provider_id: str | None,
        auth_method: AuthMethod,
        source_attempt: int,
        run_store_backend: Any,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        event_type: str = OrchestratorEventType.AUTH_SESSION_CREATED.value,
    ) -> PendingAuth:
        snapshot = engine_auth_flow_manager.start_session(
            engine=engine,
            method="auth",
            auth_method=self._map_auth_method_to_runtime(auth_method),
            provider_id=provider_id,
            transport=engine_auth_strategy_service.resolve_conversation_transport(
                engine=engine,
                provider_id=provider_id,
            ),
        )
        pending_auth = self._build_pending_auth_from_snapshot(
            snapshot=snapshot,
            auth_method=auth_method,
            source_attempt=source_attempt,
            last_error=self._normalize_string(snapshot.get("error")),
        )
        await self._persist_pending_auth(
            request_id=request_id,
            run_id=run_id,
            run_dir=run_dir,
            pending_auth=pending_auth,
            snapshot=snapshot,
            run_store_backend=run_store_backend,
            append_orchestrator_event=append_orchestrator_event,
            event_type=event_type,
        )
        log_event(
            logger,
            event="auth.session.created",
            phase="auth_orchestration",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=source_attempt,
            auth_session_id=pending_auth.auth_session_id,
            auth_method=(
                pending_auth.auth_method.value
                if pending_auth.auth_method is not None
                else None
            ),
            provider_id=pending_auth.provider_id,
            engine=engine,
        )
        return pending_auth

    async def _persist_pending_auth(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        pending_auth: PendingAuth,
        snapshot: dict[str, Any],
        run_store_backend: Any,
        append_orchestrator_event: Callable[..., None],
        event_type: str,
    ) -> None:
        await maybe_await(run_store_backend.clear_pending_auth_method_selection(request_id))
        await maybe_await(
            run_store_backend.set_pending_auth(
                request_id,
                pending_auth.model_dump(mode="json"),
                auth_resume_context=self._build_auth_resume_context(
                    snapshot=snapshot,
                    auth_method=pending_auth.auth_method,
                    source_attempt=pending_auth.source_attempt,
                ),
            )
        )
        await run_projection_service.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.WAITING_AUTH,
            current_attempt=pending_auth.source_attempt,
            pending_owner=PendingOwner.WAITING_AUTH_CHALLENGE,
            pending_auth=pending_auth.model_dump(mode="json"),
            source_attempt=pending_auth.source_attempt,
            effective_session_timeout_sec=self._positive_int_or_none(pending_auth.timeout_sec),
            run_store_backend=run_store_backend,
        )
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=pending_auth.source_attempt,
            category="interaction",
            type_name=event_type,
            data=self._build_pending_auth_event_payload(pending_auth),
        )

    async def _recover_active_pending_auth(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        engine: str,
        provider_id: str | None,
        auth_method: AuthMethod,
        source_attempt: int,
        run_store_backend: Any,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
    ) -> PendingAuth | None:
        _ = update_status
        active_snapshot = engine_auth_flow_manager.get_active_session_snapshot()
        if not bool(active_snapshot.get("active")):
            return None
        if self._normalize_string(active_snapshot.get("engine")) != engine:
            return None
        if self._normalize_string(active_snapshot.get("provider_id")) != provider_id:
            return None
        if self._normalize_string(active_snapshot.get("auth_method")) != self._map_auth_method_to_runtime(auth_method):
            return None
        pending_auth = self._build_pending_auth_from_snapshot(
            snapshot=active_snapshot,
            auth_method=auth_method,
            source_attempt=source_attempt,
            last_error=self._normalize_string(active_snapshot.get("error")),
        )
        await self._persist_pending_auth(
            request_id=request_id,
            run_id=run_id,
            run_dir=run_dir,
            pending_auth=pending_auth,
            snapshot=active_snapshot,
            run_store_backend=run_store_backend,
            append_orchestrator_event=append_orchestrator_event,
            event_type=OrchestratorEventType.AUTH_CHALLENGE_UPDATED.value,
        )
        return pending_auth

    async def _persist_method_selection(
        self,
        *,
        request_id: str,
        run_id: str,
        run_dir: Path,
        selection: PendingAuthMethodSelection,
        run_store_backend: Any,
        append_orchestrator_event: Callable[..., None],
        update_status: Callable[..., None],
        event_type: str = OrchestratorEventType.AUTH_METHOD_SELECTION_REQUIRED.value,
    ) -> None:
        await maybe_await(run_store_backend.clear_pending_auth(request_id))
        await maybe_await(run_store_backend.clear_auth_resume_context(request_id))
        await maybe_await(
            run_store_backend.set_pending_auth_method_selection(
                request_id,
                selection.model_dump(mode="json"),
            )
        )
        await run_projection_service.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.WAITING_AUTH,
            current_attempt=selection.source_attempt,
            pending_owner=PendingOwner.WAITING_AUTH_METHOD_SELECTION,
            pending_auth_method_selection=selection.model_dump(mode="json"),
            source_attempt=selection.source_attempt,
            run_store_backend=run_store_backend,
        )
        append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=selection.source_attempt,
            category="interaction",
            type_name=event_type,
            data=self._build_method_selection_event_payload(selection),
        )

    async def _schedule_resume(
        self,
        *,
        request_id: str,
        background_tasks: BackgroundTasks,
        run_store_backend: Any,
        resume_run_job: Callable[..., Any],
        target_attempt: int,
        resume_ticket_id: str,
        resume_cause: str,
    ) -> None:
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            raise HTTPException(status_code=404, detail="Request not found")
        run_id = self._normalize_string(request_record.get("run_id"))
        skill_id = self._normalize_string(request_record.get("skill_id"))
        engine_name = self._normalize_string(request_record.get("engine"))
        if run_id is None or skill_id is None or engine_name is None:
            raise HTTPException(status_code=404, detail="Run not found")
        merged_options = self._merge_request_options(request_record)
        background_tasks.add_task(
            resume_run_job,
            run_id=run_id,
            skill_id=skill_id,
            engine_name=engine_name,
            options={
                **merged_options,
                "__attempt_number_override": target_attempt,
                "__resume_ticket_id": resume_ticket_id,
                "__resume_cause": resume_cause,
            },
            cache_key=None,
        )

    async def _schedule_resume_async(
        self,
        *,
        request_id: str,
        run_store_backend: Any,
        resume_run_job: Callable[..., Any],
        target_attempt: int,
        resume_ticket_id: str,
        resume_cause: str,
    ) -> None:
        request_record = await maybe_await(run_store_backend.get_request(request_id))
        if not isinstance(request_record, dict):
            return
        run_id = self._normalize_string(request_record.get("run_id"))
        skill_id = self._normalize_string(request_record.get("skill_id"))
        engine_name = self._normalize_string(request_record.get("engine"))
        if run_id is None or skill_id is None or engine_name is None:
            return
        merged_options = self._merge_request_options(request_record)
        task = resume_run_job(
            run_id=run_id,
            skill_id=skill_id,
            engine_name=engine_name,
            options={
                **merged_options,
                "__attempt_number_override": target_attempt,
                "__resume_ticket_id": resume_ticket_id,
                "__resume_cause": resume_cause,
            },
            cache_key=None,
        )
        if asyncio.iscoroutine(task):
            asyncio.create_task(task)

    def _dispatch_engine_callback_completion(self, snapshot: dict[str, Any]) -> None:
        loop = self._callback_dispatch_loop
        if loop is None or loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(
            self._handle_engine_callback_completion(snapshot),
            loop,
        )
        future.add_done_callback(self._log_callback_dispatch_result)

    async def _handle_engine_callback_completion(self, snapshot: dict[str, Any]) -> None:
        handlers = self._resolve_runtime_handlers()
        if handlers is None:
            return
        append_orchestrator_event, update_status, resume_run_job = handlers
        await self.handle_callback_completion(
            snapshot=snapshot,
            append_orchestrator_event=append_orchestrator_event,
            update_status=update_status,
            resume_run_job=resume_run_job,
            run_store_backend=run_store,
        )

    def _capture_runtime_loop(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if loop.is_closed():
            return
        self._callback_dispatch_loop = loop

    def _resolve_runtime_handlers(
        self,
        *,
        append_orchestrator_event: Callable[..., None] | None = None,
        update_status: Callable[..., None] | None = None,
        resume_run_job: Callable[..., Any] | None = None,
    ) -> tuple[Callable[..., None], Callable[..., None], Callable[..., Any]] | None:
        if (
            append_orchestrator_event is not None
            and update_status is not None
            and resume_run_job is not None
        ):
            return append_orchestrator_event, update_status, resume_run_job
        try:
            from server.services.orchestration.job_orchestrator import job_orchestrator
        except ImportError:
            return None
        return (
            append_orchestrator_event or job_orchestrator.audit_service.append_orchestrator_event,
            update_status or job_orchestrator._update_status,
            resume_run_job or job_orchestrator.run_job,
        )

    def _log_callback_dispatch_result(self, future: concurrent.futures.Future[Any]) -> None:
        try:
            future.result()
        except Exception:
            logger.warning("engine auth callback reconciliation failed", exc_info=True)

    def _available_methods_for(self, engine: str, provider_id: str | None) -> list[AuthMethod]:
        strategy_methods = engine_auth_strategy_service.methods_for_conversation(
            engine=engine,
            provider_id=provider_id,
        )
        resolved: list[AuthMethod] = []
        for item in strategy_methods:
            method = _CONVERSATION_METHOD_MAP.get(item.strip().lower())
            if method is None:
                continue
            if method in resolved:
                continue
            resolved.append(method)
        return resolved

    def _build_method_selection(
        self,
        *,
        engine: str,
        provider_id: str | None,
        available_methods: Iterable[AuthMethod],
        source_attempt: int,
        last_error: str | None,
    ) -> PendingAuthMethodSelection:
        methods = list(available_methods)
        provider_hint = f" for provider '{provider_id}'" if provider_id else ""
        instructions = "Select an authentication method to continue."
        if last_error:
            instructions = f"{instructions} Previous error: {last_error}"
        method_labels = {
            AuthMethod.CALLBACK: "Callback URL",
            AuthMethod.DEVICE_AUTH: "Device Authorization",
            AuthMethod.AUTH_CODE_OR_URL: "Auth Code or URL",
            AuthMethod.API_KEY: "API Key",
            AuthMethod.IMPORT: "Import Credentials",
        }
        prompt_text = f"Authentication is required{provider_hint}. Choose how to continue."
        hint_text = "Choose an authentication method."
        if any(self._is_conversation_method_high_risk(engine, provider_id, method) for method in methods):
            hint_text = f"{hint_text} {_HIGH_RISK_SHORT_LABEL} {_HIGH_RISK_NOTICE}"
        ask_user = AskUserHintPayload(
            kind="choose_one",
            prompt=prompt_text,
            hint=hint_text,
            options=[
                InteractionOption(
                    label=self._render_method_label(
                        method=method,
                        base_label=method_labels.get(method, str(method.value)),
                        engine=engine,
                        provider_id=provider_id,
                    ),
                    value=method.value,
                )
                for method in methods
            ],
        )
        return PendingAuthMethodSelection(
            engine=engine,
            provider_id=provider_id,
            available_methods=methods,
            prompt=prompt_text,
            instructions=instructions,
            last_error=last_error,
            source_attempt=source_attempt,
            phase=AuthSessionPhase.METHOD_SELECTION,
            ui_hints={"widget": "choice", "hint": hint_text},
            ask_user=ask_user,
        )

    def _build_pending_auth_from_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        auth_method: AuthMethod,
        source_attempt: int,
        last_error: str | None,
    ) -> PendingAuth:
        engine = self._normalize_string(snapshot.get("engine")) or ""
        provider_id = self._normalize_string(snapshot.get("provider_id"))
        challenge_kind, accepts_chat_input, input_kind, prompt = self._challenge_profile(
            engine=engine,
            provider_id=provider_id,
            auth_method=auth_method,
            transport=engine_auth_strategy_service.resolve_conversation_transport(
                engine=engine,
                provider_id=provider_id,
            ),
            runtime_input_kind=self._normalize_string(snapshot.get("input_kind")),
        )
        return PendingAuth(
            auth_session_id=self._normalize_string(snapshot.get("session_id")) or "",
            engine=engine,
            provider_id=provider_id,
            auth_method=auth_method,
            challenge_kind=challenge_kind,
            prompt=prompt,
            auth_url=self._normalize_string(snapshot.get("auth_url")),
            user_code=self._normalize_string(snapshot.get("user_code")),
            instructions=self._build_challenge_instructions(
                challenge_kind=challenge_kind,
                auth_url=self._normalize_string(snapshot.get("auth_url")),
                user_code=self._normalize_string(snapshot.get("user_code")),
                accepts_chat_input=accepts_chat_input,
                last_error=last_error,
            ),
            accepts_chat_input=accepts_chat_input,
            input_kind=input_kind,
            last_error=last_error,
            source_attempt=source_attempt,
            phase=AuthSessionPhase.CHALLENGE_ACTIVE,
            timeout_sec=_timeout_sec_from_snapshot(snapshot),
            created_at=self._normalize_string(snapshot.get("created_at")),
            expires_at=self._normalize_string(snapshot.get("expires_at")),
        )

    def _build_import_pending_auth(
        self,
        *,
        request_id: str,
        engine: str,
        provider_id: str | None,
        source_attempt: int,
        last_error: str | None = None,
    ) -> PendingAuth:
        ask_user = self._build_import_ask_user_hint(
            engine=engine,
            provider_id=provider_id,
        )
        instructions = (
            self._append_last_error_to_instructions(
                self._normalize_string(ask_user.hint) or "Use the import action and upload required auth files.",
                last_error,
            )
        )
        return PendingAuth(
            auth_session_id=f"import::{request_id}",
            engine=engine,
            provider_id=provider_id,
            auth_method=AuthMethod.IMPORT,
            challenge_kind=AuthChallengeKind.IMPORT_FILES,
            prompt=self._normalize_string(ask_user.prompt) or "Upload credential files to complete authentication.",
            auth_url=None,
            user_code=None,
            instructions=instructions,
            accepts_chat_input=False,
            input_kind=None,
            last_error=last_error,
            source_attempt=source_attempt,
            phase=AuthSessionPhase.CHALLENGE_ACTIVE,
            timeout_sec=None,
            created_at=_utc_iso(),
            expires_at=None,
            ask_user=ask_user,
        )

    def _build_import_ask_user_hint(
        self,
        *,
        engine: str,
        provider_id: str | None,
    ) -> AskUserHintPayload:
        try:
            payload = auth_import_service.get_import_spec(
                engine=engine,
                provider_id=provider_id,
            )
        except (AuthImportError, AuthImportValidationError):
            payload = None
        ask_user = payload.get("ask_user") if isinstance(payload, dict) else None
        if isinstance(ask_user, dict):
            try:
                return AskUserHintPayload.model_validate(ask_user)
            except ValidationError:
                pass
        return AskUserHintPayload(
            kind="upload_files",
            prompt="Upload credential files to complete authentication.",
            hint="Upload required auth files to continue.",
            files=[],
            ui_hints={},
        )

    def _build_custom_provider_pending_auth(
        self,
        *,
        request_id: str,
        engine: str,
        requested_model: str,
        source_attempt: int,
        last_error: str | None = None,
    ) -> PendingAuth:
        provider_id, model_name = requested_model.split("/", 1)
        providers = engine_custom_provider_service.list_providers(engine)
        current_provider = next((item for item in providers if item.provider_id == provider_id), None)
        provider_exists = current_provider is not None
        model_exists = current_provider is not None and model_name in current_provider.models
        if provider_exists and model_exists:
            scenario = "configured_model"
        elif provider_exists:
            scenario = "provider_model_missing"
        else:
            scenario = "provider_missing"
        actions = [
            {
                "action": "replace_api_key",
                "label": "重新配置 API_KEY",
                "enabled": bool(provider_exists and model_exists),
            },
            {
                "action": "switch_model",
                "label": "切换模型",
                "enabled": bool(provider_exists),
            },
            {
                "action": "switch_provider",
                "label": "切换 provider",
                "enabled": bool(providers),
            },
            {
                "action": "configure_provider",
                "label": "配置新的 provider",
                "enabled": True,
            },
        ]
        provider_rows = [
            {
                "provider_id": item.provider_id,
                "base_url": item.base_url,
                "models": list(item.models),
            }
            for item in providers
        ]
        ask_user = AskUserHintPayload(
            kind="open_text",
            prompt="需要配置 Claude 的第三方 provider 才能继续执行。",
            hint="选择一个动作并填写字段，提交后会直接重试当前 run。",
            ui_hints={
                "widget": "provider_config",
                "scenario": scenario,
                "requested_model": requested_model,
                "requested_provider": provider_id,
                "requested_model_name": model_name,
                "providers": provider_rows,
                "current_provider": (
                    {
                        "provider_id": current_provider.provider_id,
                        "base_url": current_provider.base_url,
                        "models": list(current_provider.models),
                    }
                    if current_provider is not None
                    else None
                ),
                "actions": actions,
            },
        )
        return PendingAuth(
            auth_session_id=f"provider-config::{request_id}",
            engine=engine,
            provider_id=provider_id,
            auth_method=AuthMethod.CUSTOM_PROVIDER,
            challenge_kind=AuthChallengeKind.CUSTOM_PROVIDER,
            prompt="Claude 自定义 provider 配置是继续当前任务所必需的。",
            auth_url=None,
            user_code=None,
            instructions=self._append_last_error_to_instructions(
                "提交后会把 provider 配置写入 managed agent home，并立即重试当前 run。",
                last_error,
            ),
            accepts_chat_input=True,
            input_kind=AuthSubmissionKind.CUSTOM_PROVIDER,
            last_error=last_error,
            source_attempt=source_attempt,
            phase=AuthSessionPhase.CHALLENGE_ACTIVE,
            timeout_sec=None,
            created_at=_utc_iso(),
            expires_at=None,
            ask_user=ask_user,
        )

    def _append_last_error_to_instructions(
        self,
        instructions: str | None,
        last_error: str | None,
    ) -> str | None:
        normalized_instructions = self._normalize_string(instructions)
        normalized_last_error = self._normalize_string(last_error)
        if not normalized_last_error:
            return normalized_instructions
        if normalized_instructions and normalized_last_error in normalized_instructions:
            return normalized_instructions
        if normalized_instructions:
            return f"{normalized_instructions} Last error: {normalized_last_error}"
        return f"Last error: {normalized_last_error}"

    def _apply_last_error_to_pending_auth(
        self,
        pending_auth: PendingAuth,
        last_error: str | None,
    ) -> PendingAuth:
        normalized_last_error = self._normalize_string(last_error)
        if not normalized_last_error:
            return pending_auth
        if self._normalize_string(pending_auth.last_error):
            return pending_auth
        return pending_auth.model_copy(
            update={
                "last_error": normalized_last_error,
                "instructions": self._append_last_error_to_instructions(
                    pending_auth.instructions,
                    normalized_last_error,
                ),
            }
        )

    async def _apply_custom_provider_submission(
        self,
        *,
        request_id: str,
        request_record: dict[str, Any] | None,
        submission: str,
        run_store_backend: Any,
    ) -> None:
        if not isinstance(request_record, dict):
            raise HTTPException(status_code=404, detail="Request not found")
        engine = self._normalize_string(request_record.get("engine")) or ""
        if engine != "claude":
            raise HTTPException(status_code=422, detail="custom provider session is only supported for claude")
        payload = self._parse_custom_provider_submission(submission)
        current_engine_options_obj = request_record.get("engine_options")
        current_engine_options = (
            dict(current_engine_options_obj) if isinstance(current_engine_options_obj, dict) else {}
        )
        current_model = self._normalize_string(current_engine_options.get("model")) or ""
        current_provider_id = self._normalize_string(current_engine_options.get("provider_id"))
        providers = {
            item.provider_id: item
            for item in engine_custom_provider_service.list_providers(engine)
        }
        action = payload["action"]
        next_model = current_model
        next_provider_id = current_provider_id
        if action == "replace_api_key":
            if current_provider_id is None or current_provider_id not in providers:
                raise HTTPException(status_code=422, detail="current provider is not configured")
            current = providers[current_provider_id]
            engine_custom_provider_service.upsert_provider(
                engine=engine,
                provider_id=current.provider_id,
                api_key=payload["api_key"],
                base_url=current.base_url,
                models=list(current.models),
            )
        elif action == "switch_model":
            if current_provider_id is None or current_provider_id not in providers:
                raise HTTPException(status_code=422, detail="current provider is not configured")
            current = providers[current_provider_id]
            target_model = payload["model"]
            next_models = list(current.models)
            if target_model not in next_models:
                next_models.append(target_model)
            updated = engine_custom_provider_service.upsert_provider(
                engine=engine,
                provider_id=current.provider_id,
                api_key=current.api_key,
                base_url=current.base_url,
                models=next_models,
            )
            next_provider_id = updated.provider_id
            next_model = f"{updated.provider_id}/{target_model}"
        elif action == "switch_provider":
            target_provider_id = payload["provider_id"]
            target_model = payload["model"]
            target = providers.get(target_provider_id)
            if target is None:
                raise HTTPException(status_code=422, detail="target provider is not configured")
            next_models = list(target.models)
            if target_model not in next_models:
                next_models.append(target_model)
                target = engine_custom_provider_service.upsert_provider(
                    engine=engine,
                    provider_id=target.provider_id,
                    api_key=target.api_key,
                    base_url=target.base_url,
                    models=next_models,
                )
            next_provider_id = target.provider_id
            next_model = f"{target.provider_id}/{target_model}"
        elif action == "configure_provider":
            created = engine_custom_provider_service.upsert_provider(
                engine=engine,
                provider_id=payload["provider_id"],
                api_key=payload["api_key"],
                base_url=payload["base_url"],
                models=[payload["model"]],
            )
            next_provider_id = created.provider_id
            next_model = f"{created.provider_id}/{payload['model']}"
        else:
            raise HTTPException(status_code=422, detail="unsupported custom provider action")
        if next_model:
            if "/" in next_model:
                provider_part, model_part = next_model.split("/", 1)
                current_engine_options["provider_id"] = next_provider_id or provider_part
                current_engine_options["model"] = model_part
                current_engine_options["runtime_model"] = next_model
            else:
                current_engine_options["model"] = next_model
                if next_provider_id:
                    current_engine_options["provider_id"] = next_provider_id
            await maybe_await(run_store_backend.update_request_engine_options(request_id, current_engine_options))

    def _parse_custom_provider_submission(self, raw: str) -> dict[str, str]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="custom provider submission must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="custom provider submission must be an object")
        action = self._normalize_string(payload.get("action"))
        if action not in {
            "replace_api_key",
            "switch_model",
            "switch_provider",
            "configure_provider",
        }:
            raise HTTPException(status_code=422, detail="invalid custom provider action")
        normalized = {"action": action}
        for key in ("provider_id", "api_key", "base_url", "model"):
            value = self._normalize_string(payload.get(key))
            if value is not None:
                normalized[key] = value
        if action == "replace_api_key" and not normalized.get("api_key"):
            raise HTTPException(status_code=422, detail="api_key is required")
        if action == "switch_model" and not normalized.get("model"):
            raise HTTPException(status_code=422, detail="model is required")
        if action == "switch_provider":
            if not normalized.get("provider_id") or not normalized.get("model"):
                raise HTTPException(status_code=422, detail="provider_id and model are required")
        if action == "configure_provider":
            required = ("provider_id", "api_key", "base_url", "model")
            missing = [key for key in required if not normalized.get(key)]
            if missing:
                raise HTTPException(status_code=422, detail=f"missing fields: {', '.join(missing)}")
        return normalized

    def _build_auth_resume_context(
        self,
        *,
        snapshot: dict[str, Any],
        auth_method: AuthMethod | None,
        source_attempt: int,
    ) -> dict[str, Any]:
        return {
            "source_attempt": source_attempt,
            "runtime_input_kind": self._normalize_string(snapshot.get("input_kind")),
            "selected_method": auth_method.value if auth_method is not None else None,
        }

    def _build_pending_auth_event_payload(self, pending_auth: PendingAuth) -> dict[str, Any]:
        return pending_auth.model_dump(mode="json")

    def _build_method_selection_event_payload(
        self,
        selection: PendingAuthMethodSelection,
    ) -> dict[str, Any]:
        return selection.model_dump(mode="json")

    def _build_auth_input_accepted_payload(
        self,
        *,
        auth_session_id: str,
        submission_kind: AuthSubmissionKind,
    ) -> dict[str, Any]:
        return {
            "auth_session_id": auth_session_id,
            "submission_kind": submission_kind.value,
            "accepted_at": _utc_iso(),
        }

    def _build_auth_session_completed_payload(
        self,
        *,
        auth_session_id: str,
        source_attempt: int,
        target_attempt: int,
        resume_ticket_id: str | None,
        ticket_consumed: bool | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "auth_session_id": auth_session_id,
            "resume_attempt": target_attempt,
            "source_attempt": source_attempt,
            "target_attempt": target_attempt,
            "resume_ticket_id": resume_ticket_id,
            "ticket_consumed": ticket_consumed,
            "completed_at": _utc_iso(),
        }
        return payload

    def _build_auth_session_timed_out_payload(
        self,
        *,
        auth_session_id: str,
        request_record: dict[str, Any],
        source_attempt: int,
        reason: str,
        existing_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(existing_payload, dict):
            payload = dict(existing_payload)
            payload["last_error"] = reason
            return payload
        return {
            "auth_session_id": auth_session_id,
            "engine": str(request_record.get("engine") or ""),
            "provider_id": None,
            "auth_method": AuthMethod.CALLBACK.value,
            "challenge_kind": AuthChallengeKind.CALLBACK_URL.value,
            "prompt": "Authentication timed out.",
            "auth_url": None,
            "user_code": None,
            "instructions": reason,
            "accepts_chat_input": True,
            "input_kind": AuthSubmissionKind.CALLBACK_URL.value,
            "last_error": reason,
            "source_attempt": source_attempt,
            "phase": AuthSessionPhase.CHALLENGE_ACTIVE.value,
        }

    def _challenge_profile(
        self,
        *,
        engine: str,
        provider_id: str | None,
        auth_method: AuthMethod,
        transport: str | None = None,
        runtime_input_kind: str | None = None,
    ) -> tuple[AuthChallengeKind, bool, AuthSubmissionKind | None, str]:
        is_high_risk = self._is_conversation_method_high_risk(engine, provider_id, auth_method)
        resolved_transport = transport or engine_auth_strategy_service.resolve_conversation_transport(
            engine=engine,
            provider_id=provider_id,
        )
        session_behavior = engine_auth_strategy_service.runtime_session_behavior_for_transport(
            engine=engine,
            transport=resolved_transport,
            provider_id=provider_id,
        )

        def _append_risk(prompt: str) -> str:
            if not is_high_risk:
                return prompt
            return f"{prompt} {_HIGH_RISK_SHORT_LABEL} {_HIGH_RISK_NOTICE}"

        if auth_method == AuthMethod.CALLBACK:
            return (
                AuthChallengeKind.CALLBACK_URL,
                True,
                AuthSubmissionKind.CALLBACK_URL,
                _append_risk("Open the authorization link and paste the final callback URL here."),
            )
        if auth_method == AuthMethod.DEVICE_AUTH:
            return (
                AuthChallengeKind.OAUTH_LINK,
                False,
                None,
                _append_risk("Open the authorization link and complete device authentication in the browser."),
            )
        if auth_method == AuthMethod.AUTH_CODE_OR_URL:
            accepts_chat_input = session_behavior.input_required
            if runtime_input_kind is not None:
                accepts_chat_input = bool(runtime_input_kind)
            prompt = (
                "Open the authorization link and paste the final callback URL or authorization code here."
                if accepts_chat_input
                else "Open the authorization link and complete authentication in the browser."
            )
            return (
                AuthChallengeKind.AUTH_CODE_OR_URL,
                accepts_chat_input,
                AuthSubmissionKind.AUTH_CODE_OR_URL if accepts_chat_input else None,
                _append_risk(prompt),
            )
        if auth_method == AuthMethod.IMPORT:
            return (
                AuthChallengeKind.IMPORT_FILES,
                False,
                None,
                _append_risk("Import credential files to complete authentication."),
            )
        if auth_method == AuthMethod.CUSTOM_PROVIDER:
            return (
                AuthChallengeKind.CUSTOM_PROVIDER,
                True,
                AuthSubmissionKind.CUSTOM_PROVIDER,
                "Configure or switch the custom provider to continue.",
            )
        return (
            AuthChallengeKind.API_KEY,
            True,
            AuthSubmissionKind.API_KEY,
            _append_risk("Paste the API key here to continue."),
        )

    def _render_method_label(
        self,
        *,
        method: AuthMethod,
        base_label: str,
        engine: str,
        provider_id: str | None,
    ) -> str:
        if self._is_conversation_method_high_risk(engine, provider_id, method):
            return f"{base_label} ({_HIGH_RISK_SHORT_LABEL})"
        return base_label

    def _is_conversation_method_high_risk(
        self,
        engine: str,
        provider_id: str | None,
        method: AuthMethod,
    ) -> bool:
        return engine_auth_strategy_service.is_conversation_method_high_risk(
            engine=engine,
            provider_id=provider_id,
            conversation_method=method.value,
        )

    def _build_challenge_instructions(
        self,
        *,
        challenge_kind: AuthChallengeKind,
        auth_url: str | None,
        user_code: str | None,
        accepts_chat_input: bool,
        last_error: str | None,
    ) -> str | None:
        parts: list[str] = []
        if auth_url:
            parts.append(f"Open: {auth_url}")
        if user_code:
            parts.append(f"User code: {user_code}")
        if challenge_kind == AuthChallengeKind.CALLBACK_URL:
            parts.append("Paste the callback URL after the browser redirects.")
        elif challenge_kind == AuthChallengeKind.AUTH_CODE_OR_URL:
            if accepts_chat_input:
                parts.append("Paste the callback URL or authorization code from the browser.")
            else:
                parts.append("Complete authentication in the browser. This session will continue polling automatically.")
        elif challenge_kind == AuthChallengeKind.API_KEY:
            parts.append("Paste the API key exactly as issued by the provider.")
        if last_error:
            parts.append(f"Last error: {last_error}")
        return " ".join(part for part in parts if part) or None

    def _map_auth_method_to_runtime(self, auth_method: AuthMethod) -> str:
        if auth_method == AuthMethod.CALLBACK:
            return "callback"
        if auth_method in {AuthMethod.DEVICE_AUTH, AuthMethod.AUTH_CODE_OR_URL}:
            return "auth_code_or_url"
        if auth_method == AuthMethod.IMPORT:
            return "import"
        return "api_key"

    def _map_submission_kind_to_runtime_kind(
        self,
        *,
        submission: AuthSubmission,
        resume_context: dict[str, Any] | None,
    ) -> str:
        runtime_input_kind = self._normalize_string((resume_context or {}).get("runtime_input_kind"))
        if runtime_input_kind:
            return runtime_input_kind
        if submission.kind == AuthSubmissionKind.CALLBACK_URL:
            return "text"
        if submission.kind == AuthSubmissionKind.AUTH_CODE_OR_URL:
            return "code"
        if submission.kind == AuthSubmissionKind.IMPORT_FILES:
            return "import"
        return "api_key"

    def _snapshot_is_terminal_success(self, snapshot: dict[str, Any]) -> bool:
        status = self._normalize_string(snapshot.get("status"))
        return status in {"succeeded", "completed"}

    def _is_stale_auth_input_error(self, detail: str) -> bool:
        normalized = detail.strip().lower()
        if not normalized:
            return False
        return any(
            marker in normalized
            for marker in (
                "already finished",
                "not active",
                "does not accept input",
                "only supported for active",
                "not waiting for",
                "does not accept manual input",
            )
        )

    def _snapshot_timed_out(self, snapshot: dict[str, Any]) -> bool:
        status = self._normalize_string(snapshot.get("status"))
        if status == "expired":
            return True
        expires_at = _parse_utc(snapshot.get("expires_at"))
        return expires_at is not None and expires_at <= _utc_now()

    def _resolve_source_attempt(self, *payloads: Any) -> int:
        for payload in payloads:
            if isinstance(payload, dict):
                value = self._positive_int_or_none(payload.get("source_attempt"))
                if value is not None:
                    return value
        return 1

    def _resolve_provider_id(self, *payloads: Any) -> str | None:
        for payload in payloads:
            if isinstance(payload, dict):
                value = self._normalize_string(payload.get("provider_id"))
                if value is not None:
                    return value
        return None

    def _resolve_auth_method(self, *payloads: Any) -> AuthMethod | None:
        for payload in payloads:
            if isinstance(payload, dict):
                value = self._normalize_string(payload.get("selected_method") or payload.get("auth_method"))
                enum_value = self._enum_or_none(AuthMethod, value)
                if enum_value is not None:
                    return enum_value
        return None

    def _require_auth_method(
        self,
        auth_method: AuthMethod | None,
        *,
        submission_kind: AuthSubmissionKind | None,
    ) -> AuthMethod:
        if auth_method is not None:
            return auth_method
        if submission_kind == AuthSubmissionKind.CALLBACK_URL:
            return AuthMethod.CALLBACK
        if submission_kind == AuthSubmissionKind.AUTH_CODE_OR_URL:
            return AuthMethod.AUTH_CODE_OR_URL
        if submission_kind == AuthSubmissionKind.IMPORT_FILES:
            return AuthMethod.IMPORT
        if submission_kind == AuthSubmissionKind.CUSTOM_PROVIDER:
            return AuthMethod.CUSTOM_PROVIDER
        return AuthMethod.API_KEY

    def _merge_request_options(self, request_record: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        engine_options = request_record.get("engine_options")
        runtime_options = request_record.get(
            "effective_runtime_options",
            request_record.get("runtime_options"),
        )
        if isinstance(engine_options, dict):
            merged.update(engine_options)
        if isinstance(runtime_options, dict):
            merged.update(runtime_options)
        return merged

    def _normalize_provider_id(self, value: Any) -> str | None:
        return self._normalize_string(value)

    def _resolve_effective_provider_id(
        self,
        *,
        engine_name: str,
        auth_detection: AuthDetectionResult,
        canonical_provider_id: str | None,
        options: dict[str, Any] | None = None,
    ) -> str | None:
        normalized_engine = engine_name.strip().lower()
        if model_registry.is_multi_provider_engine(normalized_engine):
            return (
                self._normalize_provider_id(canonical_provider_id)
                or self._normalize_provider_id(auth_detection.provider_id)
                or self._provider_id_from_model_options(options)
                or self._provider_id_from_auth_detection(
                    engine_name=normalized_engine,
                    auth_detection=auth_detection,
                )
            )
        return self._normalize_provider_id(auth_detection.provider_id)

    def _provider_id_from_model_options(self, options: dict[str, Any] | None) -> str | None:
        for key in ("model", "runtime_model"):
            value = options.get(key) if isinstance(options, dict) else None
            normalized = self._normalize_string(value)
            if normalized is None or "/" not in normalized:
                continue
            provider_id, _rest = normalized.split("/", 1)
            resolved = self._normalize_provider_id(provider_id)
            if resolved is not None:
                return resolved
        return None

    def _provider_id_from_auth_detection(
        self,
        *,
        engine_name: str,
        auth_detection: AuthDetectionResult,
    ) -> str | None:
        engine_fallbacks = _AUTH_SIGNAL_PROVIDER_FALLBACKS.get(engine_name)
        if not engine_fallbacks:
            return None
        for rule_id in auth_detection.matched_rule_ids:
            provider_id = engine_fallbacks.get(rule_id.strip().lower())
            if provider_id:
                return provider_id
        return None

    def _normalize_string(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    def _positive_int_or_none(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _enum_or_none(self, enum_type: Any, value: Any) -> Any:
        if not isinstance(value, str):
            return None
        try:
            return enum_type(value)
        except ValueError:
            return None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_queued_result(self, run_dir: Path) -> None:
        result_path = run_dir / "result" / "result.json"
        try:
            result_path.unlink()
        except FileNotFoundError:
            return

    def _delete_interactions_file(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return


run_auth_orchestration_service = RunAuthOrchestrationService()
