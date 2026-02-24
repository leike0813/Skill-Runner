from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..adapters.base import RuntimeStreamParseResult
from ..models import (
    ConversationEventEnvelope,
    FcmpEventType,
    RuntimeEventCategory,
    RuntimeEventEnvelope,
    RuntimeEventRef,
    RuntimeEventSource,
)
from .engine_adapter_registry import engine_adapter_registry
from .protocol_factories import (
    make_diagnostic_warning_payload,
    make_fcmp_auto_decide_timeout,
    make_fcmp_event,
    make_fcmp_reply_accepted,
    make_fcmp_state_changed,
    make_rasp_event,
    make_terminal_failed_payload,
)
from .protocol_schema_registry import validate_fcmp_event, validate_rasp_event
from .runtime_parse_utils import stream_lines_with_offsets, strip_runtime_script_envelope


def _now() -> datetime:
    return datetime.utcnow()


def _read_bytes(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        return b""
    return path.read_bytes()


ASK_USER_BLOCK_PATTERNS = (
    re.compile(
        r"<ASK_USER_YAML>\s*[\s\S]*?\s*</ASK_USER_YAML>",
        re.IGNORECASE,
    ),
    re.compile(
        r"```(?:ask_user_yaml|ask-user-yaml)\s*[\s\S]*?```",
        re.IGNORECASE,
    ),
)


def _strip_ask_user_yaml_blocks(text: str) -> str:
    normalized = str(text or "")
    for pattern in ASK_USER_BLOCK_PATTERNS:
        normalized = pattern.sub("\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_prompt_text(text: str) -> str:
    return _strip_ask_user_yaml_blocks(text).strip()


def _extract_response_preview(payload: Mapping[str, Any]) -> Optional[str]:
    response_obj = payload.get("response")
    if isinstance(response_obj, dict):
        text_obj = response_obj.get("text")
        if isinstance(text_obj, str):
            normalized = text_obj.strip()
            return normalized or None
    if isinstance(response_obj, str):
        normalized = response_obj.strip()
        return normalized or None
    return None


def parse_engine_logs(
    *,
    engine: str,
    stdout_raw: bytes,
    stderr_raw: bytes,
    pty_raw: bytes = b"",
) -> RuntimeStreamParseResult:
    adapter = engine_adapter_registry.get(engine)
    if adapter is not None:
        return adapter.parse_runtime_stream(
            stdout_raw=stdout_raw,
            stderr_raw=stderr_raw,
            pty_raw=pty_raw,
        )
    stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
    stderr_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stderr", stderr_raw))
    pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
    raw_rows = [*stdout_rows, *stderr_rows, *pty_rows]
    return {
        "parser": "unknown",
        "confidence": 0.2,
        "session_id": None,
        "assistant_messages": [],
        "raw_rows": raw_rows,
        "diagnostics": ["UNKNOWN_ENGINE_PROFILE"],
        "structured_types": [],
    }


def _build_ref(
    *,
    attempt_number: int,
    row: Optional[Mapping[str, Any]],
) -> Optional[RuntimeEventRef]:
    if not row:
        return None
    stream = row.get("stream")
    if not isinstance(stream, str) or not stream:
        return None
    return RuntimeEventRef(
        attempt_number=attempt_number,
        stream=stream,
        byte_from=max(0, int(row.get("byte_from", 0))),
        byte_to=max(0, int(row.get("byte_to", 0))),
        encoding="utf-8",
    )


def build_rasp_events(
    *,
    run_id: str,
    engine: str,
    attempt_number: int,
    status: str,
    pending_interaction: Optional[Dict[str, Any]],
    stdout_path: Path,
    stderr_path: Path,
    pty_path: Optional[Path] = None,
    completion: Optional[Dict[str, Any]] = None,
) -> List[RuntimeEventEnvelope]:
    stdout_raw = _read_bytes(stdout_path)
    stderr_raw = _read_bytes(stderr_path)
    pty_raw = _read_bytes(pty_path) if pty_path is not None else b""
    parsed = parse_engine_logs(
        engine=engine,
        stdout_raw=stdout_raw,
        stderr_raw=stderr_raw,
        pty_raw=pty_raw,
    )

    source = RuntimeEventSource(
        engine=engine,
        parser=str(parsed["parser"]),
        confidence=float(parsed["confidence"]),
    )
    events: List[RuntimeEventEnvelope] = []

    def push(
        category: RuntimeEventCategory,
        type_name: str,
        data: Optional[Dict[str, Any]] = None,
        raw_row: Optional[Mapping[str, Any]] = None,
        correlation: Optional[Dict[str, Any]] = None,
    ) -> None:
        event_model = make_rasp_event(
            run_id=run_id,
            seq=len(events) + 1,
            source=source,
            category=category,
            type_name=type_name,
            data=data or {},
            attempt_number=attempt_number,
            raw_ref=_build_ref(attempt_number=attempt_number, row=raw_row),
            correlation=correlation or {},
            ts=_now(),
        )
        validate_rasp_event(event_model.model_dump(mode="json"))
        events.append(event_model)

    correlation: Dict[str, Any] = {}
    session_id = parsed.get("session_id")
    if isinstance(session_id, str) and session_id:
        correlation["session_id"] = session_id

    push(
        RuntimeEventCategory.LIFECYCLE,
        "lifecycle.run.status",
        data={"status": status},
        correlation=correlation,
    )
    if isinstance(completion, dict):
        state = completion.get("state")
        reason_code = completion.get("reason_code")
        if isinstance(state, str) and state:
            payload: Dict[str, Any] = {"state": state}
            if isinstance(reason_code, str) and reason_code:
                payload["reason_code"] = reason_code
            diagnostics = completion.get("diagnostics")
            if isinstance(diagnostics, list):
                payload["diagnostics"] = [item for item in diagnostics if isinstance(item, str)]
            push(
                RuntimeEventCategory.LIFECYCLE,
                "lifecycle.completion.state",
                data=payload,
                correlation=correlation,
            )

    latest_assistant_prompt = ""
    for index, msg in enumerate(parsed.get("assistant_messages", []), start=1):
        text = str(msg.get("text", ""))
        text = _normalize_prompt_text(text) or text.strip()
        if not text.strip():
            continue
        latest_assistant_prompt = text.strip()
        raw_ref_row = msg.get("raw_ref") if isinstance(msg, dict) else None
        push(
            RuntimeEventCategory.AGENT,
            "agent.message.final",
            data={
                "message_id": f"m_{attempt_number}_{index}",
                "text": text,
            },
            raw_row=raw_ref_row if isinstance(raw_ref_row, dict) else None,
            correlation=correlation,
        )

    for code in parsed.get("diagnostics", []):
        if not isinstance(code, str) or not code:
            continue
        push(
            RuntimeEventCategory.DIAGNOSTIC,
            "diagnostic.warning",
            data={"code": code},
            correlation=correlation,
        )
    if source.confidence < 0.7:
        push(
            RuntimeEventCategory.DIAGNOSTIC,
            "diagnostic.warning",
            data={"code": "LOW_CONFIDENCE_PARSE", "confidence": source.confidence},
            correlation=correlation,
        )

    for row in parsed.get("raw_rows", []):
        if not isinstance(row, dict):
            continue
        stream = str(row.get("stream", "stdout"))
        type_name = "raw.stderr" if stream == "stderr" else "raw.stdout"
        push(
            RuntimeEventCategory.RAW,
            type_name,
            data={"line": str(row.get("line", ""))},
            raw_row=row,
            correlation=correlation,
        )

    if status == "waiting_user":
        prompt = ""
        interaction_id: Optional[int] = None
        if isinstance(pending_interaction, dict):
            prompt_obj = pending_interaction.get("prompt")
            if isinstance(prompt_obj, str):
                prompt = _normalize_prompt_text(prompt_obj) or prompt_obj.strip()
            interaction_id_obj = pending_interaction.get("interaction_id")
            if isinstance(interaction_id_obj, int):
                interaction_id = interaction_id_obj
        if not prompt:
            prompt = latest_assistant_prompt
        push(
            RuntimeEventCategory.INTERACTION,
            "interaction.user_input.required",
            data={
                "interaction_id": interaction_id,
                "kind": "free_text",
                "prompt": prompt or "User input is required to continue.",
            },
            correlation=correlation,
        )
    elif status in {"failed", "canceled"}:
        push(
            RuntimeEventCategory.LIFECYCLE,
            "lifecycle.run.terminal",
            data={"status": status},
            correlation=correlation,
        )
    elif status == "succeeded":
        push(
            RuntimeEventCategory.LIFECYCLE,
            "lifecycle.run.terminal",
            data={"status": status},
            correlation=correlation,
        )

    return events


def _extract_comparable_lines(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2 and lines[0].startswith("```"):
        lines = lines[1:]
        if lines and lines[-1] == "```":
            lines = lines[:-1]
    return [line for line in lines if line]


def _suppress_duplicate_raw_echo_blocks(
    raw_events: List[RuntimeEventEnvelope],
    assistant_line_set: set[str],
    threshold: int = 3,
) -> Tuple[List[RuntimeEventEnvelope], int]:
    if not raw_events or not assistant_line_set:
        return raw_events, 0
    matched = [
        (evt.data.get("line", "").strip() in assistant_line_set) for evt in raw_events
    ]
    suppress_indexes: set[int] = set()
    index = 0
    while index < len(raw_events):
        if not matched[index]:
            index += 1
            continue
        current_ref = raw_events[index].raw_ref
        event_stream = current_ref.stream if current_ref is not None else "stdout"
        end = index + 1
        while end < len(raw_events):
            if not matched[end]:
                break
            next_ref = raw_events[end].raw_ref
            next_stream = next_ref.stream if next_ref is not None else "stdout"
            if next_stream != event_stream:
                break
            end += 1
        if end - index >= threshold:
            for cursor in range(index, end):
                suppress_indexes.add(cursor)
        index = end
    if not suppress_indexes:
        return raw_events, 0
    kept = [evt for idx, evt in enumerate(raw_events) if idx not in suppress_indexes]
    return kept, len(suppress_indexes)


def build_fcmp_events(
    rasp_events: List[RuntimeEventEnvelope],
    *,
    status: Optional[str] = None,
    status_updated_at: Optional[str] = None,
    pending_interaction: Optional[Dict[str, Any]] = None,
    interaction_history: Optional[List[Dict[str, Any]]] = None,
    orchestrator_events: Optional[List[Dict[str, Any]]] = None,
    effective_session_timeout_sec: Optional[int] = None,
    completion: Optional[Dict[str, Any]] = None,
    suppression_threshold: int = 3,
) -> List[ConversationEventEnvelope]:
    if not rasp_events:
        return []
    run_id = rasp_events[0].run_id
    engine = rasp_events[0].source.engine
    attempt_number = max(event.attempt_number for event in rasp_events)
    fcmp_events: List[ConversationEventEnvelope] = []

    def push(type_name: str, data: Dict[str, Any], raw_ref: Optional[RuntimeEventRef] = None) -> None:
        event_model = make_fcmp_event(
            run_id=run_id,
            seq=len(fcmp_events) + 1,
            engine=engine,
            type_name=type_name,
            data=data,
            attempt_number=attempt_number,
            raw_ref=raw_ref,
            ts=_now(),
        )
        validate_fcmp_event(event_model.model_dump(mode="json"))
        fcmp_events.append(event_model)

    session_id: Optional[str] = None
    for event in rasp_events:
        candidate = event.correlation.get("session_id")
        if isinstance(candidate, str) and candidate:
            session_id = candidate
            break
    if session_id:
        push(FcmpEventType.CONVERSATION_STARTED.value, {"session_id": session_id})

    assistant_events = [event for event in rasp_events if event.event.type == "agent.message.final"]
    assistant_messages: List[str] = []
    assistant_payloads: List[Tuple[str, str, Optional[RuntimeEventRef]]] = []
    for event in assistant_events:
        text = event.data.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized_text = _normalize_prompt_text(text) or text.strip()
        assistant_messages.append(normalized_text)
        message_id_obj = event.data.get("message_id")
        message_id = (
            message_id_obj
            if isinstance(message_id_obj, str) and message_id_obj.strip()
            else f"m_{attempt_number}_{len(assistant_messages)}"
        )
        assistant_payloads.append((message_id, normalized_text, event.raw_ref))

    for event in rasp_events:
        if event.event.type != "diagnostic.warning":
            continue
        code = event.data.get("code")
        if not isinstance(code, str) or not code:
            continue
        push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code}, raw_ref=event.raw_ref)

    raw_events = [event for event in rasp_events if event.event.type in {"raw.stdout", "raw.stderr"}]
    assistant_line_set: set[str] = set()
    for text in assistant_messages:
        assistant_line_set.update(_extract_comparable_lines(text))
    normalized_raw, suppressed_count = _suppress_duplicate_raw_echo_blocks(
        raw_events,
        assistant_line_set,
        threshold=max(1, int(suppression_threshold)),
    )
    if suppressed_count > 0:
        push(
            FcmpEventType.DIAGNOSTIC_WARNING.value,
            {"code": "RAW_DUPLICATE_SUPPRESSED", "suppressed_count": suppressed_count},
        )
    for event in normalized_raw:
        push(
            (
                FcmpEventType.RAW_STDERR.value
                if event.event.type == "raw.stderr"
                else FcmpEventType.RAW_STDOUT.value
            ),
            {"line": str(event.data.get("line", ""))},
            raw_ref=event.raw_ref,
        )

    effective_status = status if isinstance(status, str) and status else None
    if effective_status is None:
        for event in rasp_events:
            if event.event.type != "lifecycle.run.status":
                continue
            status_value = event.data.get("status")
            if isinstance(status_value, str) and status_value:
                effective_status = status_value
                break

    completion_state: Optional[str] = None
    completion_reason_code: Optional[str] = None
    completion_diagnostics: List[str] = []
    completion_payload = completion if isinstance(completion, dict) else None
    if completion_payload is not None:
        state_value = completion_payload.get("state")
        if isinstance(state_value, str) and state_value:
            completion_state = state_value
        reason_obj = completion_payload.get("reason_code")
        if isinstance(reason_obj, str) and reason_obj:
            completion_reason_code = reason_obj
        diagnostics_obj = completion_payload.get("diagnostics")
        if isinstance(diagnostics_obj, list):
            completion_diagnostics.extend(
                [item for item in diagnostics_obj if isinstance(item, str) and item]
            )
    else:
        for event in rasp_events:
            if event.event.type != "lifecycle.completion.state":
                continue
            state_value = event.data.get("state")
            if isinstance(state_value, str) and state_value:
                completion_state = state_value
            reason_obj = event.data.get("reason_code")
            if isinstance(reason_obj, str) and reason_obj:
                completion_reason_code = reason_obj
            diagnostics_obj = event.data.get("diagnostics")
            if isinstance(diagnostics_obj, list):
                completion_diagnostics.extend(
                    [item for item in diagnostics_obj if isinstance(item, str) and item]
                )

    history_rows = interaction_history if isinstance(interaction_history, list) else []
    current_reply_interaction_id = attempt_number - 1 if attempt_number > 1 else None
    matched_reply_row: Optional[Dict[str, Any]] = None
    for row in history_rows:
        if not isinstance(row, dict):
            continue
        if row.get("event_type") != "reply":
            continue
        interaction_id_obj = row.get("interaction_id")
        interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) and interaction_id_obj > 0 else None
        if current_reply_interaction_id is None or interaction_id != current_reply_interaction_id:
            continue
        matched_reply_row = row

    if matched_reply_row is not None:
        interaction_id_obj = matched_reply_row.get("interaction_id")
        interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) and interaction_id_obj > 0 else None
        payload_obj = matched_reply_row.get("payload")
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        resolved_at_obj = payload.get("resolved_at")
        resolved_at: Optional[str]
        if isinstance(resolved_at_obj, str) and resolved_at_obj:
            resolved_at = resolved_at_obj
        else:
            created_at_obj = matched_reply_row.get("created_at")
            resolved_at = created_at_obj if isinstance(created_at_obj, str) and created_at_obj else None
        resolution_mode_obj = payload.get("resolution_mode")
        resolution_mode = (
            resolution_mode_obj.strip()
            if isinstance(resolution_mode_obj, str) and resolution_mode_obj.strip()
            else "user_reply"
        )
        if resolution_mode == "auto_decide_timeout":
            timeout_payload = make_fcmp_auto_decide_timeout(
                interaction_id=interaction_id,
                accepted_at=resolved_at,
                policy=str(payload.get("auto_decide_policy") or "engine_judgement"),
                timeout_sec=(
                    effective_session_timeout_sec
                    if isinstance(effective_session_timeout_sec, int) and effective_session_timeout_sec > 0
                    else None
                ),
            )
            push(FcmpEventType.INTERACTION_AUTO_DECIDE_TIMEOUT.value, timeout_payload)
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="waiting_user",
                    target_state="queued",
                    trigger=FcmpEventType.INTERACTION_AUTO_DECIDE_TIMEOUT.value,
                    updated_at=resolved_at,
                    pending_interaction_id=interaction_id,
                ),
            )
        else:
            push(
                FcmpEventType.INTERACTION_REPLY_ACCEPTED.value,
                make_fcmp_reply_accepted(
                    interaction_id=interaction_id,
                    accepted_at=resolved_at,
                    response_preview=_extract_response_preview(payload),
                ),
            )
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="waiting_user",
                    target_state="queued",
                    trigger=FcmpEventType.INTERACTION_REPLY_ACCEPTED.value,
                    updated_at=resolved_at,
                    pending_interaction_id=interaction_id,
                ),
            )

    pending_payload = pending_interaction if isinstance(pending_interaction, dict) else None
    pending_interaction_id: Optional[int] = None
    if pending_payload is not None:
        interaction_id_obj = pending_payload.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            pending_interaction_id = interaction_id_obj

    state_transition_events_emitted = 0
    for row in orchestrator_events if isinstance(orchestrator_events, list) else []:
        if not isinstance(row, dict):
            continue
        type_name_obj = row.get("type")
        if not isinstance(type_name_obj, str) or not type_name_obj:
            continue
        row_data_obj = row.get("data")
        row_data = row_data_obj if isinstance(row_data_obj, dict) else {}
        row_ts_obj = row.get("ts")
        row_ts = row_ts_obj if isinstance(row_ts_obj, str) and row_ts_obj else None
        if type_name_obj == "lifecycle.run.started":
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="queued",
                    target_state="running",
                    trigger="turn.started",
                    updated_at=row_ts,
                    pending_interaction_id=None,
                ),
            )
            state_transition_events_emitted += 1
            continue
        if type_name_obj == "interaction.user_input.required":
            interaction_id_obj = row_data.get("interaction_id")
            interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) else pending_interaction_id
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="running",
                    target_state="waiting_user",
                    trigger="turn.needs_input",
                    updated_at=row_ts,
                    pending_interaction_id=interaction_id,
                ),
            )
            state_transition_events_emitted += 1
            continue
        if type_name_obj == "diagnostic.warning":
            code_obj = row_data.get("code")
            if isinstance(code_obj, str) and code_obj:
                push(
                    FcmpEventType.DIAGNOSTIC_WARNING.value,
                    make_diagnostic_warning_payload(
                        code=code_obj,
                        path=row_data.get("path") if isinstance(row_data.get("path"), str) else None,
                        detail=row_data.get("detail") if isinstance(row_data.get("detail"), str) else None,
                    ),
                )

    if state_transition_events_emitted == 0 and effective_status in {"running", "waiting_user"}:
        source_state, trigger = (
            ("queued", "turn.started")
            if effective_status == "running"
            else ("running", "turn.needs_input")
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state=source_state,
                target_state=effective_status,
                trigger=trigger,
                updated_at=status_updated_at,
                pending_interaction_id=pending_interaction_id,
            ),
        )

    for message_id, normalized_text, raw_ref in assistant_payloads:
        push(
            FcmpEventType.ASSISTANT_MESSAGE_FINAL.value,
            {
                "message_id": message_id,
                "text": normalized_text,
            },
            raw_ref=raw_ref,
        )

    terminal_state_trigger_map = {
        "succeeded": "turn.succeeded",
        "failed": "turn.failed",
        "canceled": "run.canceled",
    }
    if effective_status in terminal_state_trigger_map:
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="running",
                target_state=effective_status,
                trigger=terminal_state_trigger_map[effective_status],
                updated_at=status_updated_at,
                pending_interaction_id=None,
            ),
        )

    if completion_state == "completed":
        push(
            FcmpEventType.CONVERSATION_COMPLETED.value,
            {"state": "completed", "reason_code": completion_reason_code or "DONE_MARKER_FOUND"},
        )
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif completion_state == "interrupted":
        push(
            FcmpEventType.CONVERSATION_FAILED.value,
            {
                "error": {
                    "category": "runtime",
                    "code": completion_reason_code or "INTERRUPTED",
                }
            },
        )
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif completion_state == "awaiting_user_input" or effective_status == "waiting_user":
        prompt = ""
        waiting_interaction_id: Optional[int] = pending_interaction_id
        if pending_payload is not None:
            prompt_obj = pending_payload.get("prompt")
            if isinstance(prompt_obj, str) and prompt_obj.strip():
                prompt = _normalize_prompt_text(prompt_obj) or prompt_obj.strip()
        else:
            for event in rasp_events:
                if event.event.type != "interaction.user_input.required":
                    continue
                prompt_obj = event.data.get("prompt")
                if isinstance(prompt_obj, str) and prompt_obj.strip():
                    prompt = _normalize_prompt_text(prompt_obj) or prompt_obj.strip()
                interaction_id_obj = event.data.get("interaction_id")
                if isinstance(interaction_id_obj, int):
                    waiting_interaction_id = interaction_id_obj
                break
        if not prompt and assistant_messages:
            latest_message = assistant_messages[-1]
            if isinstance(latest_message, str) and latest_message.strip():
                prompt = latest_message.strip()
        push(
            FcmpEventType.USER_INPUT_REQUIRED.value,
            {
                "interaction_id": waiting_interaction_id,
                "kind": "free_text",
                "prompt": prompt or "User input is required to continue.",
            },
        )
        if completion_reason_code:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": completion_reason_code})
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif effective_status == "succeeded":
        push(
            FcmpEventType.CONVERSATION_COMPLETED.value,
            {"state": "completed", "reason_code": "OUTPUT_VALIDATED"},
        )
    elif effective_status in {"failed", "canceled"}:
        push(
            FcmpEventType.CONVERSATION_FAILED.value,
            make_terminal_failed_payload(code=effective_status.upper()),
        )
    elif effective_status in {"queued", "running"}:
        pass
    else:
        push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": "INCOMPLETE_STATE_CLASSIFICATION"})
    return fcmp_events


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False))
            fp.write("\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def compute_protocol_metrics(
    rasp_events: List[RuntimeEventEnvelope],
) -> Dict[str, Any]:
    total_events = len(rasp_events)
    diagnostic_count = sum(
        1
        for event in rasp_events
        if event.event.category == RuntimeEventCategory.DIAGNOSTIC
    )
    parser_warning_count = sum(
        1
        for event in rasp_events
        if event.event.type == "diagnostic.warning"
    )
    raw_count = sum(1 for event in rasp_events if event.event.category == RuntimeEventCategory.RAW)
    confidence_values = [event.source.confidence for event in rasp_events]
    avg_confidence = (
        float(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
    )
    completion_unknown = sum(
        1
        for event in rasp_events
        if event.event.type == "lifecycle.completion.state"
        and event.data.get("state") == "unknown"
    )
    parser_profile = rasp_events[0].source.parser if rasp_events else "unknown"
    return {
        "parser_profile": parser_profile,
        "event_count": total_events,
        "diagnostic_count": diagnostic_count,
        "raw_event_count": raw_count,
        "parser_fallback_count": parser_warning_count,
        "unknown_terminal_count": completion_unknown,
        "avg_confidence": avg_confidence,
    }
