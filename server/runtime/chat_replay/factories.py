from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from server.models import ChatReplayEventEnvelope, ChatReplayKind, ChatReplayRole
from server.runtime.common.ask_user_text import normalize_interaction_text


def make_chat_replay_event(
    *,
    run_id: str,
    seq: int,
    attempt: int,
    role: str,
    kind: str,
    text: str,
    created_at: datetime | None = None,
    correlation: Optional[Dict[str, Any]] = None,
) -> ChatReplayEventEnvelope:
    return ChatReplayEventEnvelope(
        run_id=run_id,
        seq=seq,
        attempt=attempt,
        role=ChatReplayRole(role),
        kind=ChatReplayKind(kind),
        text=text,
        created_at=created_at or datetime.utcnow(),
        correlation=correlation or {},
    )


def _safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _auth_submission_text(submission_kind: str) -> str:
    normalized = submission_kind.strip().lower()
    if normalized == "api_key":
        return "API key submitted"
    if normalized == "callback_url":
        return "Callback URL submitted"
    if normalized == "authorization_code":
        return "Authorization code submitted"
    return "Authentication input submitted"


def build_terminal_system_message(status: str, event_data: dict[str, Any] | None) -> str:
    payload = event_data if isinstance(event_data, dict) else {}
    terminal_obj = payload.get("terminal")
    terminal = terminal_obj if isinstance(terminal_obj, dict) else payload
    if status == "succeeded":
        return "任务已成功。"
    if status == "canceled":
        return "任务已取消。"
    if status == "failed":
        error_obj = terminal.get("error")
        error = error_obj if isinstance(error_obj, dict) else {}
        message = _safe_text(error.get("message"))
        if message:
            return f"任务失败：{message}"
        code = _safe_text(error.get("code"))
        if code:
            return f"任务失败（{code}）。"
        return "任务失败。"
    return "任务状态已更新。"


def derive_chat_replay_rows_from_fcmp(row: dict[str, Any]) -> List[dict[str, Any]]:
    type_name = _safe_text(row.get("type"))
    if not type_name:
        return []
    seq_obj = row.get("seq")
    seq = int(seq_obj) if isinstance(seq_obj, int) and seq_obj > 0 else 0
    run_id = _safe_text(row.get("run_id"))
    meta_obj = row.get("meta")
    meta = meta_obj if isinstance(meta_obj, dict) else {}
    attempt = int(meta.get("attempt") or 1)
    correlation = dict(row.get("correlation") or {})
    created_at_obj = row.get("ts")
    created_at: datetime | None = None
    if isinstance(created_at_obj, str) and created_at_obj:
        try:
            created_at = datetime.fromisoformat(created_at_obj.replace("Z", "+00:00"))
        except ValueError:
            created_at = None
    data_obj = row.get("data")
    data = data_obj if isinstance(data_obj, dict) else {}
    raw_ref_obj = row.get("raw_ref")
    if isinstance(raw_ref_obj, dict):
        correlation = {**correlation, "raw_ref": raw_ref_obj}
    specs: List[tuple[str, str, str, Dict[str, Any]]] = []

    if type_name == "interaction.reply.accepted":
        preview = _safe_text(data.get("response_preview"))
        text = preview or "Reply submitted"
        specs.append(
            (
                ChatReplayRole.USER.value,
                ChatReplayKind.INTERACTION_REPLY.value,
                text,
                {
                    "interaction_id": data.get("interaction_id"),
                    "accepted_at": data.get("accepted_at"),
                    "fcmp_seq": seq,
                },
            )
        )
    elif type_name == "auth.input.accepted":
        submission_kind = _safe_text(data.get("submission_kind")) or "authorization_code"
        specs.append(
            (
                ChatReplayRole.USER.value,
                ChatReplayKind.AUTH_SUBMISSION.value,
                _auth_submission_text(submission_kind),
                {
                    "auth_session_id": data.get("auth_session_id"),
                    "submission_kind": submission_kind,
                    "accepted_at": data.get("accepted_at"),
                    "fcmp_seq": seq,
                },
            )
        )
    elif type_name == "assistant.message.final":
        text = normalize_interaction_text(data.get("text"))
        if text:
            specs.append(
                (
                    ChatReplayRole.ASSISTANT.value,
                    ChatReplayKind.ASSISTANT_FINAL.value,
                    text,
                    {"message_id": data.get("message_id"), "fcmp_seq": seq},
                )
            )
    elif type_name == "auth.completed":
        specs.append(
            (
                ChatReplayRole.SYSTEM.value,
                ChatReplayKind.ORCHESTRATION_NOTICE.value,
                "Authentication completed. Resuming task...",
                {"auth_session_id": data.get("auth_session_id"), "fcmp_seq": seq},
            )
        )
    elif type_name == "auth.failed":
        text = _safe_text(data.get("message")) or "Authentication failed."
        specs.append(
            (
                ChatReplayRole.SYSTEM.value,
                ChatReplayKind.ORCHESTRATION_NOTICE.value,
                text,
                {"auth_session_id": data.get("auth_session_id"), "fcmp_seq": seq},
            )
        )
    elif type_name == "interaction.auto_decide.timeout":
        specs.append(
            (
                ChatReplayRole.SYSTEM.value,
                ChatReplayKind.ORCHESTRATION_NOTICE.value,
                "Timeout auto decision applied.",
                {"interaction_id": data.get("interaction_id"), "fcmp_seq": seq},
            )
        )
    elif type_name == "conversation.state.changed":
        next_status = _safe_text(data.get("to"))
        if next_status in {"succeeded", "failed", "canceled"}:
            specs.append(
                (
                    ChatReplayRole.SYSTEM.value,
                    ChatReplayKind.ORCHESTRATION_NOTICE.value,
                    build_terminal_system_message(next_status, data),
                    {"status": next_status, "fcmp_seq": seq},
                )
            )

    rows: List[dict[str, Any]] = []
    for role, kind, text, row_correlation in specs:
        if not text:
            continue
        event = make_chat_replay_event(
            run_id=run_id,
            seq=1,
            attempt=attempt,
            role=role,
            kind=kind,
            text=text,
            created_at=created_at,
            correlation={**correlation, **row_correlation},
        )
        rows.append(event.model_dump(mode="json"))
    return rows
