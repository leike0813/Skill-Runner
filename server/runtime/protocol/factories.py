from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from server.models import (
    ConversationEventEnvelope,
    FcmpEventType,
    RuntimeEventCategory,
    RuntimeEventEnvelope,
    RuntimeEventIdentity,
    RuntimeEventRef,
    RuntimeEventSource,
)


def make_rasp_event(
    *,
    run_id: str,
    seq: int,
    source: RuntimeEventSource,
    category: RuntimeEventCategory,
    type_name: str,
    data: Dict[str, Any],
    attempt_number: int,
    raw_ref: Optional[RuntimeEventRef] = None,
    correlation: Optional[Dict[str, Any]] = None,
    ts: Optional[datetime] = None,
) -> RuntimeEventEnvelope:
    return RuntimeEventEnvelope(
        run_id=run_id,
        seq=seq,
        ts=ts or datetime.utcnow(),
        source=source,
        event=RuntimeEventIdentity(category=category, type=type_name),
        data=data,
        correlation=correlation or {},
        attempt_number=attempt_number,
        raw_ref=raw_ref,
    )


def make_fcmp_event(
    *,
    run_id: str,
    seq: int,
    engine: str,
    type_name: str,
    data: Dict[str, Any],
    attempt_number: int,
    raw_ref: Optional[RuntimeEventRef] = None,
    ts: Optional[datetime] = None,
) -> ConversationEventEnvelope:
    return ConversationEventEnvelope(
        run_id=run_id,
        seq=seq,
        ts=ts or datetime.utcnow(),
        engine=engine,
        type=type_name,
        data=data,
        meta={"attempt": attempt_number},
        raw_ref=raw_ref,
    )


def make_fcmp_state_changed(
    *,
    source_state: str,
    target_state: str,
    trigger: str,
    updated_at: Optional[str],
    pending_interaction_id: Optional[int],
    pending_auth_session_id: Optional[str] = None,
    resume_cause: Optional[str] = None,
    pending_owner: Optional[str] = None,
    resume_ticket_id: Optional[str] = None,
    ticket_consumed: Optional[bool] = None,
    terminal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "from": source_state,
        "to": target_state,
        "trigger": trigger,
        "updated_at": updated_at,
        "pending_interaction_id": pending_interaction_id,
        "pending_auth_session_id": pending_auth_session_id,
    }
    if resume_cause is not None:
        payload["resume_cause"] = resume_cause
    if pending_owner is not None:
        payload["pending_owner"] = pending_owner
    if resume_ticket_id is not None:
        payload["resume_ticket_id"] = resume_ticket_id
    if ticket_consumed is not None:
        payload["ticket_consumed"] = ticket_consumed
    if terminal is not None:
        payload["terminal"] = terminal
    return payload


def make_fcmp_reply_accepted(
    *,
    interaction_id: Optional[int],
    accepted_at: Optional[str],
    response_preview: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "interaction_id": interaction_id,
        "resolution_mode": "user_reply",
        "accepted_at": accepted_at,
    }
    if isinstance(response_preview, str):
        payload["response_preview"] = response_preview
    return payload


def make_fcmp_auto_decide_timeout(
    *,
    interaction_id: Optional[int],
    accepted_at: Optional[str],
    policy: str,
    timeout_sec: Optional[int],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "interaction_id": interaction_id,
        "resolution_mode": "auto_decide_timeout",
        "accepted_at": accepted_at,
        "policy": policy,
    }
    if isinstance(timeout_sec, int) and timeout_sec > 0:
        payload["timeout_sec"] = timeout_sec
    return payload


def make_fcmp_auth_challenge(
    *,
    auth_session_id: Optional[str],
    engine: str,
    challenge_kind: Optional[str],
    prompt: str,
    provider_id: Optional[str] = None,
    auth_url: Optional[str] = None,
    user_code: Optional[str] = None,
    instructions: Optional[str] = None,
    accepts_chat_input: bool = False,
    input_kind: Optional[str] = None,
    last_error: Optional[str] = None,
    source_attempt: int = 1,
    phase: Optional[str] = None,
    available_methods: Optional[list[Any]] = None,
    ask_user: Optional[Dict[str, Any]] = None,
    auth_method: Optional[str] = None,
    timeout_sec: Optional[int] = None,
    created_at: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_phase = phase
    if normalized_phase is None and auth_session_id is not None:
        normalized_phase = "challenge_active"
    payload: Dict[str, Any] = {
        "engine": engine,
        "provider_id": provider_id,
        "prompt": prompt,
        "last_error": last_error,
        "source_attempt": source_attempt,
    }
    if auth_session_id is not None:
        payload["auth_session_id"] = auth_session_id
    if challenge_kind is not None:
        payload["challenge_kind"] = challenge_kind
    if auth_url is not None:
        payload["auth_url"] = auth_url
    if user_code is not None:
        payload["user_code"] = user_code
    if instructions is not None:
        payload["instructions"] = instructions
    if auth_method is not None:
        payload["auth_method"] = auth_method
    if normalized_phase is not None:
        payload["phase"] = normalized_phase
    if available_methods is not None:
        payload["available_methods"] = available_methods
    if isinstance(ask_user, dict):
        payload["ask_user"] = ask_user
    if challenge_kind is not None:
        payload["accepts_chat_input"] = accepts_chat_input
        payload["input_kind"] = input_kind
    if timeout_sec is not None:
        payload["timeout_sec"] = timeout_sec
    if created_at is not None:
        payload["created_at"] = created_at
    if expires_at is not None:
        payload["expires_at"] = expires_at
    return payload


def make_fcmp_auth_input_accepted(
    *,
    auth_session_id: str,
    submission_kind: str,
    accepted_at: Optional[str],
) -> Dict[str, Any]:
    return {
        "auth_session_id": auth_session_id,
        "submission_kind": submission_kind,
        "accepted_at": accepted_at,
    }


def make_fcmp_auth_completed(
    *,
    auth_session_id: str,
    completed_at: Optional[str],
    resume_attempt: Optional[int] = None,
    source_attempt: Optional[int] = None,
    target_attempt: Optional[int] = None,
    resume_ticket_id: Optional[str] = None,
    ticket_consumed: Optional[bool] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "auth_session_id": auth_session_id,
        "completed_at": completed_at,
    }
    if resume_attempt is not None:
        payload["resume_attempt"] = resume_attempt
    if source_attempt is not None:
        payload["source_attempt"] = source_attempt
    if target_attempt is not None:
        payload["target_attempt"] = target_attempt
    if resume_ticket_id is not None:
        payload["resume_ticket_id"] = resume_ticket_id
    if ticket_consumed is not None:
        payload["ticket_consumed"] = ticket_consumed
    return payload


def make_fcmp_auth_failed(
    *,
    auth_session_id: str,
    message: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"auth_session_id": auth_session_id}
    if message is not None:
        payload["message"] = message
    if code is not None:
        payload["code"] = code
    return payload


def make_diagnostic_warning_payload(
    *,
    code: str,
    path: Optional[str] = None,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"code": code}
    if path is not None:
        payload["path"] = path
    if detail is not None:
        payload["detail"] = detail
    return payload


def make_orchestrator_event(
    *,
    attempt_number: int,
    seq: int,
    category: str,
    type_name: str,
    data: Dict[str, Any],
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ts": ts or datetime.utcnow().isoformat(),
        "attempt_number": max(1, int(attempt_number)),
        "seq": max(1, int(seq)),
        "category": category,
        "type": type_name,
        "data": data,
    }


def make_resume_command(
    *,
    interaction_id: int,
    response: Any,
    resolution_mode: str,
    auto_decide_reason: Optional[str] = None,
    auto_decide_policy: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "interaction_id": int(interaction_id),
        "response": response,
        "resolution_mode": resolution_mode,
    }
    if auto_decide_reason is not None:
        payload["auto_decide_reason"] = auto_decide_reason
    if auto_decide_policy is not None:
        payload["auto_decide_policy"] = auto_decide_policy
    return payload


def make_terminal_failed_payload(*, code: str) -> Dict[str, Any]:
    return {"error": {"category": "runtime", "code": code}}


def make_fcmp_terminal_payload(
    *,
    status: str,
    code: Optional[str] = None,
    message: Optional[str] = None,
    reason_code: Optional[str] = None,
    diagnostics: Optional[list[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": status}
    if isinstance(reason_code, str) and reason_code.strip():
        payload["reason_code"] = reason_code.strip()
    if status in {"failed", "canceled"}:
        error: Dict[str, Any] = {
            "category": "runtime" if status == "failed" else "lifecycle",
            "code": code or status.upper(),
        }
        if isinstance(message, str) and message.strip():
            error["message"] = message.strip()
        payload["error"] = error
    normalized_diagnostics = [item for item in (diagnostics or []) if isinstance(item, str) and item]
    if normalized_diagnostics:
        payload["diagnostics"] = normalized_diagnostics
    return payload


def is_fcmp_state_changed(type_name: str) -> bool:
    return type_name == FcmpEventType.CONVERSATION_STATE_CHANGED.value
