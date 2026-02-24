from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..models import (
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
) -> Dict[str, Any]:
    return {
        "from": source_state,
        "to": target_state,
        "trigger": trigger,
        "updated_at": updated_at,
        "pending_interaction_id": pending_interaction_id,
    }


def make_fcmp_reply_accepted(
    *,
    interaction_id: Optional[int],
    accepted_at: Optional[str],
) -> Dict[str, Any]:
    return {
        "interaction_id": interaction_id,
        "resolution_mode": "user_reply",
        "accepted_at": accepted_at,
    }


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
    category: str,
    type_name: str,
    data: Dict[str, Any],
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ts": ts or datetime.utcnow().isoformat(),
        "attempt_number": max(1, int(attempt_number)),
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


def is_fcmp_state_changed(type_name: str) -> bool:
    return type_name == FcmpEventType.CONVERSATION_STATE_CHANGED.value
