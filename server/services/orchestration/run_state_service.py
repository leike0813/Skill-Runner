from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal
from uuid import uuid4

from server.models import (
    ClientConversationMode,
    CurrentRunProjection,
    DispatchPhase,
    ExecutionMode,
    PendingOwner,
    ResumeCause,
    RunDispatchEnvelope,
    RunPendingState,
    RunResumeState,
    RunRuntimeState,
    RunStateEnvelope,
    RunStatePhase,
    RunStatus,
    TerminalRunResult,
)
from server.runtime.protocol.schema_registry import (
    validate_current_run_projection,
    validate_run_dispatch_envelope,
    validate_run_state_envelope,
    validate_terminal_run_result,
)
from server.services.orchestration.run_execution_core import resolve_conversation_mode
from server.services.orchestration.run_store import run_store
from server.services.platform.async_compat import maybe_await


class RunStateService:
    """Single writer for .state/* and terminal result files."""

    def _backend_method(self, run_store_backend: Any, name: str) -> Any | None:
        candidate = getattr(run_store_backend, name, None)
        return candidate if callable(candidate) else None

    async def _get_run_state(self, run_store_backend: Any, request_id: str) -> Dict[str, Any] | None:
        getter = self._backend_method(run_store_backend, "get_run_state")
        if getter is None:
            return None
        payload = await maybe_await(getter(request_id))
        return dict(payload) if isinstance(payload, dict) else None

    async def _set_run_state(
        self,
        run_store_backend: Any,
        request_id: str,
        state_payload: Dict[str, Any],
    ) -> None:
        setter = self._backend_method(run_store_backend, "set_run_state")
        if setter is None:
            return
        await maybe_await(setter(request_id, state_payload))

    async def _get_dispatch_state(
        self,
        run_store_backend: Any,
        request_id: str,
    ) -> Dict[str, Any] | None:
        getter = self._backend_method(run_store_backend, "get_dispatch_state")
        if getter is None:
            return None
        payload = await maybe_await(getter(request_id))
        return dict(payload) if isinstance(payload, dict) else None

    async def _set_dispatch_state(
        self,
        run_store_backend: Any,
        request_id: str,
        dispatch_payload: Dict[str, Any],
    ) -> None:
        setter = self._backend_method(run_store_backend, "set_dispatch_state")
        if setter is None:
            return
        await maybe_await(setter(request_id, dispatch_payload))

    async def _update_run_status(
        self,
        run_store_backend: Any,
        run_id: str,
        status: RunStatus,
    ) -> None:
        updater = self._backend_method(run_store_backend, "update_run_status")
        if updater is None:
            return
        await maybe_await(updater(run_id, status))

    async def _set_current_projection(
        self,
        run_store_backend: Any,
        request_id: str,
        projection_payload: Dict[str, Any],
    ) -> None:
        setter = self._backend_method(run_store_backend, "set_current_projection")
        if setter is None:
            return
        await maybe_await(setter(request_id, projection_payload))

    def _state_path(self, run_dir: Path) -> Path:
        return run_dir / ".state" / "state.json"

    def _dispatch_path(self, run_dir: Path) -> Path:
        return run_dir / ".state" / "dispatch.json"

    def _result_path(self, run_dir: Path) -> Path:
        return run_dir / "result" / "result.json"

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json_dict(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _delete(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def read_state_file(self, run_dir: Path) -> Dict[str, Any]:
        return self._read_json_dict(self._state_path(run_dir))

    def read_dispatch_file(self, run_dir: Path) -> Dict[str, Any]:
        return self._read_json_dict(self._dispatch_path(run_dir))

    def _runtime_context(self, request_record: Dict[str, Any] | None) -> RunRuntimeState:
        request_payload = request_record or {}
        runtime_options = request_payload.get("runtime_options", {})
        effective_runtime_options = request_payload.get("effective_runtime_options", runtime_options)
        requested_execution_mode = runtime_options.get("execution_mode")
        effective_execution_mode = effective_runtime_options.get("execution_mode")
        conversation_mode = resolve_conversation_mode(request_payload.get("client_metadata"))
        if isinstance(requested_execution_mode, str):
            requested = ExecutionMode(requested_execution_mode)
        else:
            requested = None
        if isinstance(effective_execution_mode, str):
            effective = ExecutionMode(effective_execution_mode)
        else:
            effective = None
        timeout_obj = effective_runtime_options.get("interactive_reply_timeout_sec")
        timeout_value = timeout_obj if isinstance(timeout_obj, int) and timeout_obj >= 0 else None
        return RunRuntimeState(
            conversation_mode=ClientConversationMode(conversation_mode),
            requested_execution_mode=requested,
            effective_execution_mode=effective,
            effective_interactive_require_user_reply=bool(
                effective == ExecutionMode.INTERACTIVE
                and conversation_mode == ClientConversationMode.SESSION.value
            ),
            effective_interactive_reply_timeout_sec=timeout_value,
        )

    def _build_pending_state(
        self,
        *,
        pending_owner: PendingOwner | None,
        pending_interaction: Dict[str, Any] | None,
        pending_auth: Dict[str, Any] | None,
        pending_auth_method_selection: Dict[str, Any] | None,
    ) -> RunPendingState:
        if pending_owner == PendingOwner.WAITING_USER and isinstance(pending_interaction, dict):
            interaction_id_obj = pending_interaction.get("interaction_id")
            interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) else None
            return RunPendingState(
                owner=pending_owner,
                interaction_id=interaction_id,
                payload=dict(pending_interaction),
            )
        if pending_owner == PendingOwner.WAITING_AUTH_CHALLENGE and isinstance(pending_auth, dict):
            auth_session_id = pending_auth.get("auth_session_id")
            return RunPendingState(
                owner=pending_owner,
                auth_session_id=auth_session_id if isinstance(auth_session_id, str) else None,
                payload=dict(pending_auth),
            )
        if (
            pending_owner == PendingOwner.WAITING_AUTH_METHOD_SELECTION
            and isinstance(pending_auth_method_selection, dict)
        ):
            return RunPendingState(owner=pending_owner, payload=dict(pending_auth_method_selection))
        return RunPendingState()

    def _build_resume_state(
        self,
        *,
        resume_ticket_id: str | None,
        resume_cause: ResumeCause | None,
        source_attempt: int | None,
        target_attempt: int | None,
    ) -> RunResumeState:
        return RunResumeState(
            resume_ticket_id=resume_ticket_id,
            resume_cause=resume_cause,
            source_attempt=source_attempt,
            target_attempt=target_attempt,
        )

    def _state_to_projection(self, state_payload: Dict[str, Any]) -> Dict[str, Any]:
        pending_obj = state_payload.get("pending")
        resume_obj = state_payload.get("resume")
        runtime_obj = state_payload.get("runtime")
        pending: Dict[str, Any] = pending_obj if isinstance(pending_obj, dict) else {}
        resume: Dict[str, Any] = resume_obj if isinstance(resume_obj, dict) else {}
        runtime: Dict[str, Any] = runtime_obj if isinstance(runtime_obj, dict) else {}
        pending_owner_raw = pending.get("owner")
        resume_cause_raw = resume.get("resume_cause")
        conversation_mode_raw = runtime.get("conversation_mode")
        requested_execution_mode_raw = runtime.get("requested_execution_mode")
        effective_execution_mode_raw = runtime.get("effective_execution_mode")
        projection = CurrentRunProjection(
            request_id=str(state_payload.get("request_id") or ""),
            run_id=str(state_payload.get("run_id") or ""),
            status=RunStatus(str(state_payload.get("status") or RunStatus.QUEUED.value)),
            updated_at=datetime.fromisoformat(str(state_payload.get("updated_at"))),
            current_attempt=int(state_payload.get("current_attempt") or 1),
            pending_owner=PendingOwner(str(pending_owner_raw)) if isinstance(pending_owner_raw, str) else None,
            pending_interaction_id=pending.get("interaction_id") if isinstance(pending.get("interaction_id"), int) else None,
            pending_auth_session_id=pending.get("auth_session_id") if isinstance(pending.get("auth_session_id"), str) else None,
            resume_ticket_id=resume.get("resume_ticket_id") if isinstance(resume.get("resume_ticket_id"), str) else None,
            resume_cause=ResumeCause(str(resume_cause_raw)) if isinstance(resume_cause_raw, str) else None,
            source_attempt=resume.get("source_attempt") if isinstance(resume.get("source_attempt"), int) else None,
            target_attempt=resume.get("target_attempt") if isinstance(resume.get("target_attempt"), int) else None,
            conversation_mode=ClientConversationMode(str(conversation_mode_raw)) if isinstance(conversation_mode_raw, str) else None,
            requested_execution_mode=ExecutionMode(str(requested_execution_mode_raw)) if isinstance(requested_execution_mode_raw, str) else None,
            effective_execution_mode=ExecutionMode(str(effective_execution_mode_raw)) if isinstance(effective_execution_mode_raw, str) else None,
            effective_interactive_require_user_reply=runtime.get("effective_interactive_require_user_reply")
            if isinstance(runtime.get("effective_interactive_require_user_reply"), bool)
            else None,
            effective_interactive_reply_timeout_sec=runtime.get("effective_interactive_reply_timeout_sec")
            if isinstance(runtime.get("effective_interactive_reply_timeout_sec"), int)
            else None,
            effective_session_timeout_sec=runtime.get("effective_session_timeout_sec")
            if isinstance(runtime.get("effective_session_timeout_sec"), int)
            else None,
            error=state_payload.get("error"),
            warnings=list(state_payload.get("warnings") or []),
        ).model_dump(mode="json")
        return projection

    async def initialize_queued_state(
        self,
        *,
        run_dir: Path,
        request_id: str,
        run_id: str,
        request_record: Dict[str, Any] | None = None,
        run_store_backend: Any = run_store,
    ) -> Dict[str, Any]:
        updated_at = datetime.utcnow()
        state_model = RunStateEnvelope(
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.QUEUED,
            updated_at=updated_at,
            current_attempt=0,
            state_phase=RunStatePhase(dispatch_phase=DispatchPhase.CREATED),
            pending=RunPendingState(),
            resume=RunResumeState(),
            runtime=self._runtime_context(request_record),
        )
        state_payload = state_model.model_dump(mode="json")
        validate_run_state_envelope(state_payload)
        await self._set_run_state(run_store_backend, request_id, state_payload)
        await self._update_run_status(run_store_backend, run_id, RunStatus.QUEUED)
        self._write_json(self._state_path(run_dir), state_payload)
        projection_payload = self._state_to_projection(state_payload)
        validate_current_run_projection(projection_payload)
        await self._set_current_projection(run_store_backend, request_id, projection_payload)
        dispatch_payload = await self.advance_dispatch_phase(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            phase=DispatchPhase.CREATED,
            run_store_backend=run_store_backend,
        )
        return {"state": state_payload, "dispatch": dispatch_payload}

    async def advance_dispatch_phase(
        self,
        *,
        run_dir: Path,
        request_id: str,
        run_id: str,
        phase: DispatchPhase,
        dispatch_ticket_id: str | None = None,
        worker_claim_id: str | None = None,
        last_error: str | None = None,
        run_store_backend: Any = run_store,
    ) -> Dict[str, Any]:
        existing = await self._get_dispatch_state(run_store_backend, request_id) or {}
        now = datetime.utcnow()
        dispatch_model = RunDispatchEnvelope(
            request_id=request_id,
            run_id=run_id,
            dispatch_ticket_id=dispatch_ticket_id or str(existing.get("dispatch_ticket_id") or uuid4()),
            phase=phase,
            worker_claim_id=worker_claim_id or existing.get("worker_claim_id"),
            admitted_at=(
                now
                if phase == DispatchPhase.ADMITTED and existing.get("admitted_at") is None
                else self._parse_datetime(existing.get("admitted_at"))
            ),
            scheduled_at=(
                now
                if phase == DispatchPhase.DISPATCH_SCHEDULED and existing.get("scheduled_at") is None
                else self._parse_datetime(existing.get("scheduled_at"))
            ),
            claimed_at=(
                now
                if phase in {DispatchPhase.WORKER_CLAIMED, DispatchPhase.ATTEMPT_MATERIALIZING}
                and existing.get("claimed_at") is None
                else self._parse_datetime(existing.get("claimed_at"))
            ),
            last_error=last_error or existing.get("last_error"),
            updated_at=now,
        )
        dispatch_payload = dispatch_model.model_dump(mode="json")
        validate_run_dispatch_envelope(dispatch_payload)
        await self._set_dispatch_state(run_store_backend, request_id, dispatch_payload)
        self._write_json(self._dispatch_path(run_dir), dispatch_payload)
        state_payload = await self._get_run_state(run_store_backend, request_id)
        if isinstance(state_payload, dict):
            state_payload = dict(state_payload)
            state_phase_obj = state_payload.get("state_phase")
            phase_payload: Dict[str, Any] = dict(state_phase_obj) if isinstance(state_phase_obj, dict) else {}
            phase_payload["dispatch_phase"] = phase.value
            state_payload["state_phase"] = phase_payload
            state_payload["updated_at"] = now.isoformat()
            await self._set_run_state(run_store_backend, request_id, state_payload)
            self._write_json(self._state_path(run_dir), state_payload)
            projection_payload = self._state_to_projection(state_payload)
            validate_current_run_projection(projection_payload)
            await self._set_current_projection(run_store_backend, request_id, projection_payload)
        return dispatch_payload

    async def claim_dispatch(
        self,
        *,
        run_dir: Path,
        request_id: str,
        run_id: str,
        worker_claim_id: str | None = None,
        run_store_backend: Any = run_store,
    ) -> Dict[str, Any]:
        return await self.advance_dispatch_phase(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            phase=DispatchPhase.WORKER_CLAIMED,
            worker_claim_id=worker_claim_id or str(uuid4()),
            run_store_backend=run_store_backend,
        )

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    async def write_non_terminal_projection(
        self,
        *,
        run_dir: Path,
        request_id: str,
        run_id: str,
        status: RunStatus,
        request_record: Dict[str, Any] | None = None,
        current_attempt: int | None = None,
        pending_owner: PendingOwner | None = None,
        pending_interaction: Dict[str, Any] | None = None,
        pending_auth: Dict[str, Any] | None = None,
        pending_auth_method_selection: Dict[str, Any] | None = None,
        resume_ticket_id: str | None = None,
        resume_cause: ResumeCause | None = None,
        source_attempt: int | None = None,
        target_attempt: int | None = None,
        effective_session_timeout_sec: int | None = None,
        error: Any = None,
        warnings: list[Any] | None = None,
        run_store_backend: Any = run_store,
    ) -> Dict[str, Any]:
        updated_at = datetime.utcnow()
        existing_state = await self._get_run_state(run_store_backend, request_id) or self.read_state_file(run_dir)
        runtime_state = self._runtime_context(request_record) if isinstance(request_record, dict) else RunRuntimeState.model_validate(
            existing_state.get("runtime") or {}
        )
        if effective_session_timeout_sec is not None:
            runtime_state.effective_session_timeout_sec = effective_session_timeout_sec
        state_phase_obj = existing_state.get("state_phase")
        phase_payload: Dict[str, Any] = dict(state_phase_obj) if isinstance(state_phase_obj, dict) else {}
        existing_resume_obj = existing_state.get("resume")
        existing_resume: Dict[str, Any] = (
            dict(existing_resume_obj) if isinstance(existing_resume_obj, dict) else {}
        )
        if status != RunStatus.QUEUED:
            phase_payload["dispatch_phase"] = None
        if pending_owner == PendingOwner.WAITING_AUTH_METHOD_SELECTION:
            phase_payload["waiting_auth_phase"] = "method_selection"
        elif pending_owner == PendingOwner.WAITING_AUTH_CHALLENGE:
            phase_payload["waiting_auth_phase"] = "challenge_active"
        else:
            phase_payload["waiting_auth_phase"] = None
        state_model = RunStateEnvelope(
            request_id=request_id,
            run_id=run_id,
            status=status,
            updated_at=updated_at,
            current_attempt=current_attempt if current_attempt is not None else int(existing_state.get("current_attempt") or 1),
            state_phase=RunStatePhase(
                waiting_auth_phase=phase_payload.get("waiting_auth_phase"),
                dispatch_phase=DispatchPhase(phase_payload["dispatch_phase"])
                if isinstance(phase_payload.get("dispatch_phase"), str)
                else None,
            ),
            pending=self._build_pending_state(
                pending_owner=pending_owner,
                pending_interaction=pending_interaction,
                pending_auth=pending_auth,
                pending_auth_method_selection=pending_auth_method_selection,
            ),
            resume=self._build_resume_state(
                resume_ticket_id=resume_ticket_id if resume_ticket_id is not None else existing_resume.get("resume_ticket_id"),
                resume_cause=resume_cause
                if resume_cause is not None
                else (
                    ResumeCause(existing_resume.get("resume_cause"))
                    if isinstance(existing_resume.get("resume_cause"), str)
                    else None
                ),
                source_attempt=source_attempt if source_attempt is not None else existing_resume.get("source_attempt"),
                target_attempt=target_attempt if target_attempt is not None else existing_resume.get("target_attempt"),
            ),
            runtime=runtime_state,
            error=error,
            warnings=list(warnings or []),
        )
        state_payload = state_model.model_dump(mode="json")
        validate_run_state_envelope(state_payload)
        await self._set_run_state(run_store_backend, request_id, state_payload)
        await self._update_run_status(run_store_backend, run_id, status)
        self._write_json(self._state_path(run_dir), state_payload)
        projection_payload = self._state_to_projection(state_payload)
        validate_current_run_projection(projection_payload)
        await self._set_current_projection(run_store_backend, request_id, projection_payload)
        self._delete(self._result_path(run_dir))
        return state_payload

    async def write_terminal_projection(
        self,
        *,
        run_dir: Path,
        request_id: str,
        run_id: str,
        status: RunStatus,
        terminal_result: Dict[str, Any],
        request_record: Dict[str, Any] | None = None,
        current_attempt: int | None = None,
        effective_session_timeout_sec: int | None = None,
        error: Any = None,
        warnings: list[Any] | None = None,
        run_store_backend: Any = run_store,
    ) -> Dict[str, Any]:
        state_payload = await self.write_non_terminal_projection(
            run_dir=run_dir,
            request_id=request_id,
            run_id=run_id,
            status=status,
            request_record=request_record,
            current_attempt=current_attempt,
            pending_owner=None,
            pending_interaction=None,
            pending_auth=None,
            pending_auth_method_selection=None,
            resume_ticket_id=None,
            resume_cause=None,
            source_attempt=None,
            target_attempt=None,
            effective_session_timeout_sec=effective_session_timeout_sec,
            error=error,
            warnings=warnings,
            run_store_backend=run_store_backend,
        )
        terminal_status: Literal["success", "succeeded", "failed", "canceled"]
        if status == RunStatus.SUCCEEDED:
            terminal_status = "success"
        elif status == RunStatus.FAILED:
            terminal_status = "failed"
        elif status == RunStatus.CANCELED:
            terminal_status = "canceled"
        else:
            terminal_status = "succeeded"
        terminal_model = TerminalRunResult(status=terminal_status, **terminal_result)
        terminal_payload = terminal_model.model_dump(mode="json")
        validate_terminal_run_result(terminal_payload)
        self._write_json(self._result_path(run_dir), terminal_payload)
        return state_payload


run_state_service = RunStateService()
