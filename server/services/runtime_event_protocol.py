from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..adapters.base import RuntimeStreamParseResult
from ..models import (
    ConversationEventEnvelope,
    RuntimeEventCategory,
    RuntimeEventEnvelope,
    RuntimeEventIdentity,
    RuntimeEventRef,
    RuntimeEventSource,
)
from .engine_adapter_registry import engine_adapter_registry
from .runtime_parse_utils import stream_lines_with_offsets, strip_runtime_script_envelope


def _now() -> datetime:
    return datetime.utcnow()


def _read_bytes(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        return b""
    return path.read_bytes()


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
        events.append(
            RuntimeEventEnvelope(
                run_id=run_id,
                seq=len(events) + 1,
                ts=_now(),
                source=source,
                event=RuntimeEventIdentity(category=category, type=type_name),
                data=data or {},
                correlation=correlation or {},
                attempt_number=attempt_number,
                raw_ref=_build_ref(attempt_number=attempt_number, row=raw_row),
            )
        )

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

    for index, msg in enumerate(parsed.get("assistant_messages", []), start=1):
        text = str(msg.get("text", ""))
        if not text.strip():
            continue
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
                prompt = prompt_obj
            interaction_id_obj = pending_interaction.get("interaction_id")
            if isinstance(interaction_id_obj, int):
                interaction_id = interaction_id_obj
        push(
            RuntimeEventCategory.INTERACTION,
            "interaction.user_input.required",
            data={
                "interaction_id": interaction_id,
                "kind": "free_text",
                "prompt": prompt or "Provide next user turn",
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
    suppression_threshold: int = 3,
) -> List[ConversationEventEnvelope]:
    if not rasp_events:
        return []
    run_id = rasp_events[0].run_id
    engine = rasp_events[0].source.engine
    attempt_number = max(event.attempt_number for event in rasp_events)
    fcmp_events: List[ConversationEventEnvelope] = []

    def push(type_name: str, data: Dict[str, Any], raw_ref: Optional[RuntimeEventRef] = None) -> None:
        fcmp_events.append(
            ConversationEventEnvelope(
                run_id=run_id,
                seq=len(fcmp_events) + 1,
                ts=_now(),
                engine=engine,
                type=type_name,
                data=data,
                meta={"attempt": attempt_number},
                raw_ref=raw_ref,
            )
        )

    session_id: Optional[str] = None
    for event in rasp_events:
        candidate = event.correlation.get("session_id")
        if isinstance(candidate, str) and candidate:
            session_id = candidate
            break
    if session_id:
        push("conversation.started", {"session_id": session_id})

    assistant_events = [
        event for event in rasp_events if event.event.type == "agent.message.final"
    ]
    assistant_messages: List[str] = []
    for event in assistant_events:
        text = event.data.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        assistant_messages.append(text)
        message_id = event.data.get("message_id")
        push(
            "assistant.message.final",
            {
                "message_id": message_id if isinstance(message_id, str) else f"m_{attempt_number}_{len(assistant_messages)}",
                "text": text,
            },
            raw_ref=event.raw_ref,
        )

    for event in rasp_events:
        if event.event.type != "diagnostic.warning":
            continue
        code = event.data.get("code")
        if not isinstance(code, str) or not code:
            continue
        push("diagnostic.warning", {"code": code}, raw_ref=event.raw_ref)

    raw_events = [
        event
        for event in rasp_events
        if event.event.type in {"raw.stdout", "raw.stderr"}
    ]
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
            "diagnostic.warning",
            {"code": "RAW_DUPLICATE_SUPPRESSED", "suppressed_count": suppressed_count},
        )
    for event in normalized_raw:
        push(
            "raw.stderr" if event.event.type == "raw.stderr" else "raw.stdout",
            {"line": str(event.data.get("line", ""))},
            raw_ref=event.raw_ref,
        )

    terminal_status = None
    completion_state: Optional[str] = None
    completion_reason_code: Optional[str] = None
    completion_diagnostics: List[str] = []
    for event in rasp_events:
        if event.event.type == "lifecycle.completion.state":
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
        if event.event.type == "lifecycle.run.status":
            status_value = event.data.get("status")
            if isinstance(status_value, str):
                terminal_status = status_value
    if completion_state == "completed":
        push(
            "conversation.completed",
            {"state": "completed", "reason_code": completion_reason_code or "DONE_MARKER_FOUND"},
        )
        for code in completion_diagnostics:
            push("diagnostic.warning", {"code": code})
    elif completion_state == "interrupted":
        push(
            "conversation.failed",
            {
                "error": {
                    "category": "runtime",
                    "code": completion_reason_code or "INTERRUPTED",
                }
            },
        )
        for code in completion_diagnostics:
            push("diagnostic.warning", {"code": code})
    elif completion_state == "awaiting_user_input" or terminal_status == "waiting_user":
        prompt = "Provide next user turn"
        interaction_id: Optional[int] = None
        for event in rasp_events:
            if event.event.type == "interaction.user_input.required":
                prompt_obj = event.data.get("prompt")
                if isinstance(prompt_obj, str) and prompt_obj.strip():
                    prompt = prompt_obj
                interaction_id_obj = event.data.get("interaction_id")
                if isinstance(interaction_id_obj, int):
                    interaction_id = interaction_id_obj
                break
        push(
            "user.input.required",
            {
                "interaction_id": interaction_id,
                "kind": "free_text",
                "prompt": prompt,
            },
        )
        if completion_reason_code:
            push("diagnostic.warning", {"code": completion_reason_code})
        for code in completion_diagnostics:
            push("diagnostic.warning", {"code": code})
    elif terminal_status == "succeeded":
        push("conversation.completed", {"state": "completed", "reason_code": "OUTPUT_VALIDATED"})
    elif terminal_status in {"failed", "canceled"}:
        push(
            "conversation.failed",
            {
                "error": {
                    "category": "runtime",
                    "code": terminal_status.upper(),
                }
            },
        )
    else:
        push("diagnostic.warning", {"code": "INCOMPLETE_STATE_CLASSIFICATION"})
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
