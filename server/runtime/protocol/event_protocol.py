from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from server.runtime.adapter.types import RuntimeStreamParseResult, RuntimeStreamRawRow
from server.runtime.common.ask_user_text import normalize_interaction_text
from server.runtime.protocol.contracts import RuntimeParserResolverPort
from server.models import (
    ConversationEventEnvelope,
    FcmpEventType,
    OrchestratorEventType,
    RuntimeEventCategory,
    RuntimeEventEnvelope,
    RuntimeEventRef,
    RuntimeEventSource,
)
from .factories import (
    make_diagnostic_warning_payload,
    make_fcmp_auth_challenge,
    make_fcmp_auth_completed,
    make_fcmp_auth_failed,
    make_fcmp_auth_input_accepted,
    make_fcmp_auto_decide_timeout,
    make_fcmp_event,
    make_fcmp_reply_accepted,
    make_fcmp_state_changed,
    make_fcmp_terminal_payload,
    make_rasp_event,
)
from .schema_registry import validate_fcmp_event, validate_rasp_event
from .parse_utils import stream_lines_with_offsets, strip_runtime_script_envelope
from .rasp_canonicalizer import coalesce_rasp_raw_rows


class _EngineAdapterRegistryShim:
    def __init__(self) -> None:
        self._resolver: RuntimeParserResolverPort | None = None

    def configure(self, resolver: RuntimeParserResolverPort | None) -> None:
        self._resolver = resolver

    def get(self, engine: str):
        if self._resolver is None:
            return None
        return self._resolver.resolve(engine)


engine_adapter_registry = _EngineAdapterRegistryShim()

def configure_runtime_parser_resolver(resolver: RuntimeParserResolverPort | None) -> None:
    engine_adapter_registry.configure(resolver)


def _now() -> datetime:
    return datetime.utcnow()


def _read_bytes(path: Path) -> bytes:
    if not path.exists() or not path.is_file():
        return b""
    return path.read_bytes()


def _normalize_prompt_text(text: str) -> str:
    return normalize_interaction_text(text)


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
    parser_resolver: RuntimeParserResolverPort | None = None,
) -> RuntimeStreamParseResult:
    adapter = parser_resolver.resolve(engine) if parser_resolver is not None else engine_adapter_registry.get(engine)
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
    parser_resolver: RuntimeParserResolverPort | None = None,
) -> List[RuntimeEventEnvelope]:
    stdout_raw = _read_bytes(stdout_path)
    stderr_raw = _read_bytes(stderr_path)
    pty_raw = _read_bytes(pty_path) if pty_path is not None else b""
    parsed = parse_engine_logs(
        engine=engine,
        stdout_raw=stdout_raw,
        stderr_raw=stderr_raw,
        pty_raw=pty_raw,
        parser_resolver=parser_resolver,
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

    structured_payloads = parsed.get("structured_payloads", [])
    if isinstance(structured_payloads, list):
        for structured_payload in structured_payloads:
            if not isinstance(structured_payload, dict):
                continue
            type_name_obj = structured_payload.get("type")
            if not isinstance(type_name_obj, str) or not type_name_obj.strip():
                continue
            type_name = type_name_obj.strip()
            stream_obj = structured_payload.get("stream")
            if not isinstance(stream_obj, str) or not stream_obj.strip():
                continue
            raw_ref_obj = structured_payload.get("raw_ref")
            structured_data: dict[str, Any] = {"stream": stream_obj}
            for key in ("session_id", "response", "summary"):
                value = structured_payload.get(key)
                if value is None or isinstance(value, str):
                    structured_data[key] = value
            details_obj = structured_payload.get("details")
            if isinstance(details_obj, dict):
                structured_data["details"] = details_obj
            push(
                RuntimeEventCategory.AGENT,
                type_name,
                data=structured_data,
                raw_row=raw_ref_obj if isinstance(raw_ref_obj, dict) else None,
                correlation=correlation,
            )

    raw_rows_obj = parsed.get("raw_rows", [])
    raw_rows_input: list[RuntimeStreamRawRow] = []
    if isinstance(raw_rows_obj, list):
        for row in raw_rows_obj:
            if not isinstance(row, dict):
                continue
            stream_obj = row.get("stream")
            line_obj = row.get("line")
            byte_from_obj = row.get("byte_from")
            byte_to_obj = row.get("byte_to")
            if not isinstance(stream_obj, str) or not isinstance(line_obj, str):
                continue
            if not isinstance(byte_from_obj, int) or not isinstance(byte_to_obj, int):
                continue
            raw_rows_input.append(
                {
                    "stream": stream_obj,
                    "line": line_obj,
                    "byte_from": byte_from_obj,
                    "byte_to": byte_to_obj,
                }
            )
    coalesced_rows, coalesce_stats = coalesce_rasp_raw_rows(raw_rows_input)
    if coalesce_stats["coalesced"] < coalesce_stats["original"]:
        push(
            RuntimeEventCategory.DIAGNOSTIC,
            "diagnostic.warning",
            data={
                "code": "RAW_STDERR_COALESCED",
                "original_rows": coalesce_stats["original"],
                "coalesced_rows": coalesce_stats["coalesced"],
            },
            correlation=correlation,
        )

    for row in coalesced_rows:
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


def translate_orchestrator_event_to_fcmp_specs(
    *,
    engine: str,
    type_name: str,
    data: Mapping[str, Any],
    updated_at: str | None,
    default_attempt_number: int,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    def push(spec_type: str, payload: Dict[str, Any]) -> None:
        specs.append({"type_name": spec_type, "data": payload})

    if type_name == OrchestratorEventType.LIFECYCLE_RUN_STARTED.value:
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="queued",
                target_state="running",
                trigger="turn.started",
                updated_at=updated_at,
                pending_interaction_id=None,
            ),
        )
        return specs

    if type_name == OrchestratorEventType.INTERACTION_USER_INPUT_REQUIRED.value:
        interaction_id_obj = data.get("interaction_id")
        interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) else None
        prompt_obj = data.get("prompt")
        prompt = (
            _normalize_prompt_text(prompt_obj) or prompt_obj.strip()
            if isinstance(prompt_obj, str) and prompt_obj.strip()
            else "User input is required to continue."
        )
        kind_obj = data.get("kind")
        kind = kind_obj if isinstance(kind_obj, str) and kind_obj.strip() else "free_text"
        push(
            FcmpEventType.USER_INPUT_REQUIRED.value,
            {
                "interaction_id": interaction_id,
                "kind": kind,
                "prompt": prompt,
            },
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="running",
                target_state="waiting_user",
                trigger="turn.needs_input",
                updated_at=updated_at,
                pending_interaction_id=interaction_id,
                pending_owner="waiting_user",
            ),
        )
        return specs

    if type_name == OrchestratorEventType.INTERACTION_REPLY_ACCEPTED.value:
        interaction_id_obj = data.get("interaction_id")
        interaction_id = interaction_id_obj if isinstance(interaction_id_obj, int) and interaction_id_obj > 0 else None
        if interaction_id is None:
            return specs
        accepted_at = data.get("accepted_at") if isinstance(data.get("accepted_at"), str) else updated_at
        response_preview = (
            data.get("response_preview")
            if isinstance(data.get("response_preview"), str)
            else _extract_response_preview(data)
        )
        push(
            FcmpEventType.INTERACTION_REPLY_ACCEPTED.value,
            make_fcmp_reply_accepted(
                interaction_id=interaction_id,
                accepted_at=accepted_at,
                response_preview=response_preview,
            ),
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="waiting_user",
                target_state="queued",
                trigger=FcmpEventType.INTERACTION_REPLY_ACCEPTED.value,
                updated_at=accepted_at,
                pending_interaction_id=interaction_id,
                resume_cause="interaction_reply",
                pending_owner="waiting_user",
            ),
        )
        return specs

    if type_name in {
        OrchestratorEventType.AUTH_SESSION_CREATED.value,
        OrchestratorEventType.AUTH_METHOD_SELECTION_REQUIRED.value,
    }:
        source_attempt_obj = data.get("source_attempt")
        source_attempt = (
            source_attempt_obj
            if isinstance(source_attempt_obj, int) and source_attempt_obj > 0
            else default_attempt_number
        )
        auth_session_id_obj = data.get("auth_session_id")
        auth_session_id = (
            auth_session_id_obj.strip()
            if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
            else None
        )
        push(
            FcmpEventType.AUTH_REQUIRED.value,
            make_fcmp_auth_challenge(
                auth_session_id=auth_session_id,
                engine=str(data.get("engine") or engine),
                provider_id=data.get("provider_id") if isinstance(data.get("provider_id"), str) else None,
                challenge_kind=data.get("challenge_kind") if isinstance(data.get("challenge_kind"), str) else None,
                prompt=str(data.get("prompt") or "Authentication is required to continue."),
                auth_url=data.get("auth_url") if isinstance(data.get("auth_url"), str) else None,
                user_code=data.get("user_code") if isinstance(data.get("user_code"), str) else None,
                instructions=data.get("instructions") if isinstance(data.get("instructions"), str) else None,
                accepts_chat_input=bool(data.get("accepts_chat_input")),
                input_kind=data.get("input_kind") if isinstance(data.get("input_kind"), str) else None,
                last_error=data.get("last_error") if isinstance(data.get("last_error"), str) else None,
                source_attempt=source_attempt,
                phase=data.get("phase") if isinstance(data.get("phase"), str) else None,
                available_methods=data.get("available_methods") if isinstance(data.get("available_methods"), list) else None,
                ask_user=data.get("ask_user") if isinstance(data.get("ask_user"), dict) else None,
                auth_method=data.get("auth_method") if isinstance(data.get("auth_method"), str) else None,
                timeout_sec=data.get("timeout_sec") if isinstance(data.get("timeout_sec"), int) else None,
                created_at=data.get("created_at") if isinstance(data.get("created_at"), str) else None,
                expires_at=data.get("expires_at") if isinstance(data.get("expires_at"), str) else None,
            ),
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="running",
                target_state="waiting_auth",
                trigger=FcmpEventType.AUTH_REQUIRED.value,
                updated_at=updated_at,
                pending_interaction_id=None,
                pending_auth_session_id=auth_session_id,
                pending_owner=(
                    "waiting_auth.method_selection"
                    if type_name == OrchestratorEventType.AUTH_METHOD_SELECTION_REQUIRED.value
                    else "waiting_auth.challenge_active"
                ),
            ),
        )
        return specs

    if type_name in {
        OrchestratorEventType.AUTH_CHALLENGE_UPDATED.value,
        OrchestratorEventType.AUTH_METHOD_SELECTED.value,
        OrchestratorEventType.AUTH_SESSION_TIMED_OUT.value,
    }:
        source_attempt_obj = data.get("source_attempt")
        source_attempt = (
            source_attempt_obj
            if isinstance(source_attempt_obj, int) and source_attempt_obj > 0
            else default_attempt_number
        )
        push(
            FcmpEventType.AUTH_CHALLENGE_UPDATED.value,
            make_fcmp_auth_challenge(
                auth_session_id=data.get("auth_session_id") if isinstance(data.get("auth_session_id"), str) else None,
                engine=str(data.get("engine") or engine),
                provider_id=data.get("provider_id") if isinstance(data.get("provider_id"), str) else None,
                challenge_kind=data.get("challenge_kind") if isinstance(data.get("challenge_kind"), str) else None,
                prompt=str(data.get("prompt") or "Authentication is required to continue."),
                auth_url=data.get("auth_url") if isinstance(data.get("auth_url"), str) else None,
                user_code=data.get("user_code") if isinstance(data.get("user_code"), str) else None,
                instructions=data.get("instructions") if isinstance(data.get("instructions"), str) else None,
                accepts_chat_input=bool(data.get("accepts_chat_input")),
                input_kind=data.get("input_kind") if isinstance(data.get("input_kind"), str) else None,
                last_error=data.get("last_error") if isinstance(data.get("last_error"), str) else None,
                source_attempt=source_attempt,
                phase=data.get("phase") if isinstance(data.get("phase"), str) else None,
                available_methods=data.get("available_methods") if isinstance(data.get("available_methods"), list) else None,
                ask_user=data.get("ask_user") if isinstance(data.get("ask_user"), dict) else None,
                auth_method=data.get("auth_method") if isinstance(data.get("auth_method"), str) else None,
                timeout_sec=data.get("timeout_sec") if isinstance(data.get("timeout_sec"), int) else None,
                created_at=data.get("created_at") if isinstance(data.get("created_at"), str) else None,
                expires_at=data.get("expires_at") if isinstance(data.get("expires_at"), str) else None,
            ),
        )
        return specs

    if type_name == OrchestratorEventType.AUTH_SESSION_BUSY.value:
        push(
            FcmpEventType.DIAGNOSTIC_WARNING.value,
            make_diagnostic_warning_payload(
                code="AUTH_SESSION_BUSY",
                detail=(
                    data.get("last_error")
                    if isinstance(data.get("last_error"), str)
                    else str(data.get("instructions") or "Auth session is already active.")
                ),
            ),
        )
        return specs

    if type_name == OrchestratorEventType.AUTH_INPUT_ACCEPTED.value:
        auth_session_id_obj = data.get("auth_session_id")
        auth_session_id = (
            auth_session_id_obj.strip()
            if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
            else None
        )
        if auth_session_id is None:
            return specs
        push(
            FcmpEventType.AUTH_INPUT_ACCEPTED.value,
            make_fcmp_auth_input_accepted(
                auth_session_id=auth_session_id,
                submission_kind=str(data.get("submission_kind") or "authorization_code"),
                accepted_at=(
                    data.get("accepted_at")
                    if isinstance(data.get("accepted_at"), str)
                    else updated_at
                ),
            ),
        )
        return specs

    if type_name == OrchestratorEventType.AUTH_SESSION_COMPLETED.value:
        auth_session_id_obj = data.get("auth_session_id")
        auth_session_id = (
            auth_session_id_obj.strip()
            if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
            else None
        )
        if auth_session_id is None:
            return specs
        target_attempt_obj = data.get("target_attempt")
        resume_attempt_obj = data.get("resume_attempt")
        if isinstance(target_attempt_obj, int) and target_attempt_obj > 0:
            target_attempt = target_attempt_obj
        elif isinstance(resume_attempt_obj, int) and resume_attempt_obj > 0:
            target_attempt = resume_attempt_obj
        else:
            target_attempt = default_attempt_number + 1
        source_attempt_obj = data.get("source_attempt")
        source_attempt = (
            source_attempt_obj
            if isinstance(source_attempt_obj, int) and source_attempt_obj > 0
            else default_attempt_number
        )
        push(
            FcmpEventType.AUTH_COMPLETED.value,
            make_fcmp_auth_completed(
                auth_session_id=auth_session_id,
                completed_at=(
                    data.get("completed_at")
                    if isinstance(data.get("completed_at"), str)
                    else updated_at
                ),
                resume_attempt=target_attempt,
                source_attempt=source_attempt,
                target_attempt=target_attempt,
                resume_ticket_id=data.get("resume_ticket_id") if isinstance(data.get("resume_ticket_id"), str) else None,
                ticket_consumed=(
                    bool(data.get("ticket_consumed"))
                    if isinstance(data.get("ticket_consumed"), bool)
                    else None
                ),
            ),
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="waiting_auth",
                target_state="queued",
                trigger=FcmpEventType.AUTH_COMPLETED.value,
                updated_at=updated_at,
                pending_interaction_id=None,
                pending_auth_session_id=auth_session_id,
                resume_cause="auth_completed",
                pending_owner="waiting_auth.challenge_active",
                resume_ticket_id=data.get("resume_ticket_id") if isinstance(data.get("resume_ticket_id"), str) else None,
                ticket_consumed=(
                    bool(data.get("ticket_consumed"))
                    if isinstance(data.get("ticket_consumed"), bool)
                    else None
                ),
            ),
        )
        return specs

    if type_name == OrchestratorEventType.AUTH_SESSION_FAILED.value:
        auth_session_id_obj = data.get("auth_session_id")
        auth_session_id = (
            auth_session_id_obj.strip()
            if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
            else None
        )
        if auth_session_id is None:
            return specs
        message = data.get("last_error") if isinstance(data.get("last_error"), str) else None
        push(
            FcmpEventType.AUTH_FAILED.value,
            make_fcmp_auth_failed(
                auth_session_id=auth_session_id,
                message=(
                    data.get("message")
                    if isinstance(data.get("message"), str)
                    else message
                ),
                code=(
                    data.get("code")
                    if isinstance(data.get("code"), str)
                    else "AUTH_FAILED"
                ),
            ),
        )
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="waiting_auth",
                target_state="failed",
                trigger=FcmpEventType.AUTH_FAILED.value,
                updated_at=updated_at,
                pending_interaction_id=None,
                pending_auth_session_id=auth_session_id,
                terminal=make_fcmp_terminal_payload(
                    status="failed",
                    code="AUTH_FAILED",
                    reason_code="AUTH_FAILED",
                    message=message,
                ),
            ),
        )
        return specs

    if type_name in {
        OrchestratorEventType.LIFECYCLE_RUN_TERMINAL.value,
        OrchestratorEventType.LIFECYCLE_RUN_CANCELED.value,
    }:
        status = str(data.get("status") or "").strip().lower()
        trigger = "turn.failed"
        message = data.get("message") if isinstance(data.get("message"), str) else None
        code = data.get("code") if isinstance(data.get("code"), str) else None
        if type_name == OrchestratorEventType.LIFECYCLE_RUN_CANCELED.value:
            status = "canceled"
            trigger = "run.canceled"
        elif status == "succeeded":
            trigger = "turn.succeeded"
        elif status == "canceled":
            trigger = "run.canceled"
        elif status != "failed":
            return specs
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="running",
                target_state=status,
                trigger=trigger,
                updated_at=updated_at,
                pending_interaction_id=None,
                terminal=make_fcmp_terminal_payload(
                    status=status,
                    code=code or status.upper(),
                    reason_code=code or status.upper(),
                    message=message,
                ),
            ),
        )
        return specs

    if type_name == OrchestratorEventType.ERROR_RUN_FAILED.value:
        message = data.get("message") if isinstance(data.get("message"), str) else None
        code = data.get("code") if isinstance(data.get("code"), str) else "ORCHESTRATOR_ERROR"
        push(
            FcmpEventType.DIAGNOSTIC_WARNING.value,
            make_diagnostic_warning_payload(
                code=code,
                detail=message,
            ),
        )
        return specs

    if type_name == OrchestratorEventType.DIAGNOSTIC_WARNING.value:
        code_obj = data.get("code")
        if not isinstance(code_obj, str) or not code_obj:
            return specs
        push(
            FcmpEventType.DIAGNOSTIC_WARNING.value,
            make_diagnostic_warning_payload(
                code=code_obj,
                path=data.get("path") if isinstance(data.get("path"), str) else None,
                detail=data.get("detail") if isinstance(data.get("detail"), str) else None,
            ),
        )
        return specs

    return specs


def build_fcmp_events(
    rasp_events: List[RuntimeEventEnvelope],
    *,
    status: Optional[str] = None,
    status_updated_at: Optional[str] = None,
    pending_interaction: Optional[Dict[str, Any]] = None,
    pending_auth_method_selection: Optional[Dict[str, Any]] = None,
    pending_auth: Optional[Dict[str, Any]] = None,
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
    matched_reply_row: Optional[Dict[str, Any]] = None
    for row in history_rows:
        if not isinstance(row, dict):
            continue
        if row.get("event_type") != "reply":
            continue
        source_attempt_obj = row.get("source_attempt")
        source_attempt = (
            source_attempt_obj
            if isinstance(source_attempt_obj, int) and source_attempt_obj > 0
            else None
        )
        if source_attempt is None or source_attempt + 1 != attempt_number:
            continue
        matched_reply_row = row
        break

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
                    resume_cause="interaction_auto_decide_timeout",
                    pending_owner="waiting_user",
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
                    resume_cause="interaction_reply",
                    pending_owner="waiting_user",
                ),
            )

    pending_payload = pending_interaction if isinstance(pending_interaction, dict) else None
    pending_auth_selection_payload = (
        pending_auth_method_selection if isinstance(pending_auth_method_selection, dict) else None
    )
    pending_auth_payload = pending_auth if isinstance(pending_auth, dict) else None
    pending_interaction_id: Optional[int] = None
    pending_auth_session_id: Optional[str] = None
    if pending_payload is not None:
        interaction_id_obj = pending_payload.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            pending_interaction_id = interaction_id_obj
    if pending_auth_payload is not None:
        auth_session_id_obj = pending_auth_payload.get("auth_session_id")
        if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip():
            pending_auth_session_id = auth_session_id_obj.strip()
    pending_owner: Optional[str] = None
    if pending_payload is not None:
        pending_owner = "waiting_user"
    elif pending_auth_selection_payload is not None:
        pending_owner = "waiting_auth.method_selection"
    elif pending_auth_payload is not None:
        pending_owner = "waiting_auth.challenge_active"

    state_transition_events_emitted = 0
    terminal_state_emitted = False
    auth_required_emitted = False
    auth_completed_emitted = False
    auth_failed_emitted = False
    started_emitted = False
    auth_completed_keys: set[tuple[str, int | None]] = set()
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
            if started_emitted:
                continue
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
            started_emitted = True
            state_transition_events_emitted += 1
            continue
        if type_name_obj == "lifecycle.run.terminal":
            status_obj = row_data.get("status")
            status = (
                status_obj.strip().lower()
                if isinstance(status_obj, str) and status_obj.strip()
                else (
                    effective_status
                    if effective_status in {"succeeded", "failed", "canceled"}
                    else None
                )
            )
            if status not in {"succeeded", "failed", "canceled"}:
                continue
            trigger_map = {
                "succeeded": "turn.succeeded",
                "failed": "turn.failed",
                "canceled": "run.canceled",
            }
            reason_code_obj = row_data.get("code")
            reason_code = reason_code_obj if isinstance(reason_code_obj, str) and reason_code_obj.strip() else None
            message = row_data.get("message") if isinstance(row_data.get("message"), str) else None
            orchestrator_terminal_payload = make_fcmp_terminal_payload(
                status=status,
                code=reason_code or status.upper(),
                reason_code=reason_code or status.upper(),
                message=message,
                diagnostics=completion_diagnostics,
            )
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="running",
                    target_state=status,
                    trigger=trigger_map[status],
                    updated_at=row_ts,
                    pending_interaction_id=None,
                    terminal=orchestrator_terminal_payload,
                ),
            )
            state_transition_events_emitted += 1
            terminal_state_emitted = True
            continue
        if type_name_obj == "error.run.failed":
            code_obj = row_data.get("code")
            warning_code = code_obj if isinstance(code_obj, str) and code_obj.strip() else "ORCHESTRATOR_ERROR"
            detail = row_data.get("message") if isinstance(row_data.get("message"), str) else None
            push(
                FcmpEventType.DIAGNOSTIC_WARNING.value,
                make_diagnostic_warning_payload(
                    code=warning_code,
                    detail=detail,
                ),
            )
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
        if type_name_obj in {
            "auth.session.created",
            "auth.challenge.updated",
            "auth.method.selection.required",
            "auth.method.selected",
            "auth.session.timed_out",
        }:
            fallback_auth_payload = pending_auth_payload or pending_auth_selection_payload
            auth_payload: dict[str, Any] | None
            if isinstance(row_data, dict) and row_data:
                auth_payload = dict(fallback_auth_payload) if isinstance(fallback_auth_payload, dict) else {}
                for key, value in row_data.items():
                    if value is None:
                        continue
                    if isinstance(value, str) and not value.strip():
                        continue
                    auth_payload[key] = value
            else:
                auth_payload = (
                    dict(fallback_auth_payload)
                    if isinstance(fallback_auth_payload, dict)
                    else None
                )
            if not isinstance(auth_payload, dict):
                continue
            auth_session_id_obj = auth_payload.get("auth_session_id")
            auth_session_id = None
            if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip():
                auth_session_id = auth_session_id_obj.strip()
                pending_auth_session_id = auth_session_id
            challenge_payload = make_fcmp_auth_challenge(
                auth_session_id=auth_session_id,
                engine=str(auth_payload.get("engine") or engine),
                provider_id=auth_payload.get("provider_id") if isinstance(auth_payload.get("provider_id"), str) else None,
                challenge_kind=(
                    auth_payload.get("challenge_kind")
                    if isinstance(auth_payload.get("challenge_kind"), str)
                    else None
                ),
                prompt=str(auth_payload.get("prompt") or "Authentication is required to continue."),
                auth_url=auth_payload.get("auth_url") if isinstance(auth_payload.get("auth_url"), str) else None,
                user_code=auth_payload.get("user_code") if isinstance(auth_payload.get("user_code"), str) else None,
                instructions=auth_payload.get("instructions") if isinstance(auth_payload.get("instructions"), str) else None,
                accepts_chat_input=bool(auth_payload.get("accepts_chat_input")),
                input_kind=auth_payload.get("input_kind") if isinstance(auth_payload.get("input_kind"), str) else None,
                last_error=auth_payload.get("last_error") if isinstance(auth_payload.get("last_error"), str) else None,
                source_attempt=int(auth_payload.get("source_attempt") or attempt_number),
                phase=auth_payload.get("phase") if isinstance(auth_payload.get("phase"), str) else None,
                available_methods=(
                    auth_payload.get("available_methods")
                    if isinstance(auth_payload.get("available_methods"), list)
                    else None
                ),
                ask_user=auth_payload.get("ask_user") if isinstance(auth_payload.get("ask_user"), dict) else None,
                auth_method=auth_payload.get("auth_method") if isinstance(auth_payload.get("auth_method"), str) else None,
                timeout_sec=auth_payload.get("timeout_sec") if isinstance(auth_payload.get("timeout_sec"), int) else None,
                created_at=auth_payload.get("created_at") if isinstance(auth_payload.get("created_at"), str) else None,
                expires_at=auth_payload.get("expires_at") if isinstance(auth_payload.get("expires_at"), str) else None,
            )
            if type_name_obj in {"auth.session.created", "auth.method.selection.required"}:
                push(FcmpEventType.AUTH_REQUIRED.value, challenge_payload)
                push(
                    FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                    make_fcmp_state_changed(
                        source_state="running",
                        target_state="waiting_auth",
                        trigger=FcmpEventType.AUTH_REQUIRED.value,
                        updated_at=row_ts,
                        pending_interaction_id=None,
                        pending_auth_session_id=auth_session_id,
                        pending_owner=(
                            "waiting_auth.method_selection"
                            if type_name_obj == "auth.method.selection.required"
                            else "waiting_auth.challenge_active"
                        ),
                    ),
                )
                auth_required_emitted = True
                state_transition_events_emitted += 1
            else:
                push(FcmpEventType.AUTH_CHALLENGE_UPDATED.value, challenge_payload)
            continue
        if type_name_obj == "auth.session.busy":
            push(
                FcmpEventType.DIAGNOSTIC_WARNING.value,
                make_diagnostic_warning_payload(
                    code="AUTH_SESSION_BUSY",
                    detail=(
                        row_data.get("last_error")
                        if isinstance(row_data.get("last_error"), str)
                        else (
                            row_data.get("instructions")
                            if isinstance(row_data.get("instructions"), str)
                            else "Auth session is already active."
                        )
                    ),
                ),
            )
            continue
        if type_name_obj == "auth.input.accepted":
            auth_session_id_obj = row_data.get("auth_session_id")
            auth_session_id = (
                auth_session_id_obj.strip()
                if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
                else pending_auth_session_id
            )
            if not auth_session_id:
                continue
            pending_auth_session_id = auth_session_id
            push(
                FcmpEventType.AUTH_INPUT_ACCEPTED.value,
                make_fcmp_auth_input_accepted(
                    auth_session_id=auth_session_id,
                    submission_kind=str(row_data.get("submission_kind") or "authorization_code"),
                    accepted_at=(
                        row_data.get("accepted_at")
                        if isinstance(row_data.get("accepted_at"), str)
                        else row_ts
                    ),
                ),
            )
            continue
        if type_name_obj == "auth.session.completed":
            auth_session_id_obj = row_data.get("auth_session_id")
            auth_session_id = (
                auth_session_id_obj.strip()
                if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
                else pending_auth_session_id
            )
            if not auth_session_id:
                continue
            resume_attempt_obj = row_data.get("target_attempt", row_data.get("resume_attempt"))
            resume_attempt = (
                int(resume_attempt_obj)
                if isinstance(resume_attempt_obj, int) and resume_attempt_obj > 0
                else attempt_number + 1
            )
            auth_completed_key = (auth_session_id, resume_attempt)
            if auth_completed_key in auth_completed_keys:
                continue
            auth_completed_keys.add(auth_completed_key)
            pending_auth_session_id = auth_session_id
            push(
                FcmpEventType.AUTH_COMPLETED.value,
                make_fcmp_auth_completed(
                    auth_session_id=auth_session_id,
                    completed_at=(
                        row_data.get("completed_at")
                        if isinstance(row_data.get("completed_at"), str)
                        else row_ts
                    ),
                    resume_attempt=resume_attempt,
                    source_attempt=(
                        row_data.get("source_attempt")
                        if isinstance(row_data.get("source_attempt"), int)
                        else attempt_number
                    ),
                    target_attempt=resume_attempt,
                    resume_ticket_id=(
                        str(row_data.get("resume_ticket_id"))
                        if isinstance(row_data.get("resume_ticket_id"), str)
                        else None
                    ),
                    ticket_consumed=(
                        bool(row_data.get("ticket_consumed"))
                        if isinstance(row_data.get("ticket_consumed"), bool)
                        else None
                    ),
                ),
            )
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="waiting_auth",
                    target_state="queued",
                    trigger=FcmpEventType.AUTH_COMPLETED.value,
                    updated_at=row_ts,
                    pending_interaction_id=None,
                    pending_auth_session_id=auth_session_id,
                    resume_cause="auth_completed",
                    pending_owner="waiting_auth.challenge_active",
                    resume_ticket_id=(
                        str(row_data.get("resume_ticket_id"))
                        if isinstance(row_data.get("resume_ticket_id"), str)
                        else None
                    ),
                    ticket_consumed=(
                        bool(row_data.get("ticket_consumed"))
                        if isinstance(row_data.get("ticket_consumed"), bool)
                        else None
                    ),
                ),
            )
            auth_completed_emitted = True
            state_transition_events_emitted += 1
            continue
        if type_name_obj == "auth.session.failed":
            auth_session_id_obj = row_data.get("auth_session_id")
            auth_session_id = (
                auth_session_id_obj.strip()
                if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
                else pending_auth_session_id
            )
            if not auth_session_id:
                continue
            pending_auth_session_id = auth_session_id
            push(
                FcmpEventType.AUTH_FAILED.value,
                make_fcmp_auth_failed(
                    auth_session_id=auth_session_id,
                    message=(
                        row_data.get("message")
                        if isinstance(row_data.get("message"), str)
                        else (
                            row_data.get("last_error")
                            if isinstance(row_data.get("last_error"), str)
                            else None
                        )
                    ),
                    code=(
                        row_data.get("code")
                        if isinstance(row_data.get("code"), str)
                        else "AUTH_FAILED"
                    ),
                ),
            )
            push(
                FcmpEventType.CONVERSATION_STATE_CHANGED.value,
                make_fcmp_state_changed(
                    source_state="waiting_auth",
                    target_state="failed",
                    trigger=FcmpEventType.AUTH_FAILED.value,
                    updated_at=row_ts,
                    pending_interaction_id=None,
                    pending_auth_session_id=auth_session_id,
                ),
            )
            auth_failed_emitted = True
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

    if state_transition_events_emitted == 0 and effective_status in {"running", "waiting_user", "waiting_auth"}:
        if effective_status == "running":
            source_state, trigger = ("queued", "turn.started")
        elif effective_status == "waiting_user":
            source_state, trigger = ("running", "turn.needs_input")
        else:
            source_state, trigger = ("running", FcmpEventType.AUTH_REQUIRED.value)
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state=source_state,
                target_state=effective_status,
                trigger=trigger,
                updated_at=status_updated_at,
                pending_interaction_id=pending_interaction_id,
                pending_auth_session_id=pending_auth_session_id,
                pending_owner=pending_owner,
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
    terminal_payload: Optional[Dict[str, Any]] = None
    if effective_status == "succeeded":
        terminal_payload = make_fcmp_terminal_payload(
            status="succeeded",
            reason_code=completion_reason_code or "OUTPUT_VALIDATED",
            diagnostics=completion_diagnostics,
        )
    elif effective_status in {"failed", "canceled"}:
        terminal_payload = make_fcmp_terminal_payload(
            status=effective_status,
            code=completion_reason_code or effective_status.upper(),
            reason_code=completion_reason_code or effective_status.upper(),
            diagnostics=completion_diagnostics,
        )
    if effective_status in terminal_state_trigger_map and not terminal_state_emitted:
        push(
            FcmpEventType.CONVERSATION_STATE_CHANGED.value,
            make_fcmp_state_changed(
                source_state="running",
                target_state=effective_status,
                trigger=terminal_state_trigger_map[effective_status],
                updated_at=status_updated_at,
                pending_interaction_id=None,
                terminal=terminal_payload,
            ),
        )

    if effective_status in {"failed", "canceled"}:
        if completion_state == "completed":
            push(
                FcmpEventType.DIAGNOSTIC_WARNING.value,
                {"code": "TERMINAL_STATUS_COMPLETION_CONFLICT"},
            )
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif effective_status == "succeeded":
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif completion_state == "interrupted" and effective_status not in {"waiting_user", "waiting_auth"}:
        push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": completion_reason_code or "INTERRUPTED"})
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
    elif effective_status == "waiting_auth":
        auth_waiting_payload = pending_auth_payload or pending_auth_selection_payload
        if auth_waiting_payload is not None and not auth_required_emitted:
            auth_session_id_obj = auth_waiting_payload.get("auth_session_id")
            auth_session_id = (
                auth_session_id_obj.strip()
                if isinstance(auth_session_id_obj, str) and auth_session_id_obj.strip()
                else pending_auth_session_id
            )
            push(
                FcmpEventType.AUTH_REQUIRED.value,
                make_fcmp_auth_challenge(
                    auth_session_id=auth_session_id,
                    engine=str(auth_waiting_payload.get("engine") or engine),
                    provider_id=auth_waiting_payload.get("provider_id") if isinstance(auth_waiting_payload.get("provider_id"), str) else None,
                    challenge_kind=auth_waiting_payload.get("challenge_kind") if isinstance(auth_waiting_payload.get("challenge_kind"), str) else None,
                    prompt=str(auth_waiting_payload.get("prompt") or "Authentication is required to continue."),
                    auth_url=auth_waiting_payload.get("auth_url") if isinstance(auth_waiting_payload.get("auth_url"), str) else None,
                    user_code=auth_waiting_payload.get("user_code") if isinstance(auth_waiting_payload.get("user_code"), str) else None,
                    instructions=auth_waiting_payload.get("instructions") if isinstance(auth_waiting_payload.get("instructions"), str) else None,
                    accepts_chat_input=bool(auth_waiting_payload.get("accepts_chat_input")),
                    input_kind=auth_waiting_payload.get("input_kind") if isinstance(auth_waiting_payload.get("input_kind"), str) else None,
                    last_error=auth_waiting_payload.get("last_error") if isinstance(auth_waiting_payload.get("last_error"), str) else None,
                    source_attempt=int(auth_waiting_payload.get("source_attempt") or attempt_number),
                    phase=auth_waiting_payload.get("phase") if isinstance(auth_waiting_payload.get("phase"), str) else None,
                    available_methods=(
                        auth_waiting_payload.get("available_methods")
                        if isinstance(auth_waiting_payload.get("available_methods"), list)
                        else None
                    ),
                    ask_user=(
                        auth_waiting_payload.get("ask_user")
                        if isinstance(auth_waiting_payload.get("ask_user"), dict)
                        else None
                    ),
                    auth_method=auth_waiting_payload.get("auth_method") if isinstance(auth_waiting_payload.get("auth_method"), str) else None,
                    timeout_sec=auth_waiting_payload.get("timeout_sec") if isinstance(auth_waiting_payload.get("timeout_sec"), int) else None,
                    created_at=auth_waiting_payload.get("created_at") if isinstance(auth_waiting_payload.get("created_at"), str) else None,
                    expires_at=auth_waiting_payload.get("expires_at") if isinstance(auth_waiting_payload.get("expires_at"), str) else None,
                ),
            )
        if completion_reason_code:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": completion_reason_code})
        for code in completion_diagnostics:
            push(FcmpEventType.DIAGNOSTIC_WARNING.value, {"code": code})
    elif effective_status in {"queued", "running"} or auth_completed_emitted or auth_failed_emitted:
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
    decoder = json.JSONDecoder()

    def _decode_dicts_best_effort(text: str) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        index = 0
        text_len = len(text)
        while index < text_len:
            while index < text_len and text[index].isspace():
                index += 1
            if index >= text_len:
                break
            try:
                payload, end_index = decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                break
            if isinstance(payload, dict):
                parsed.append(payload)
            index = end_index
        return parsed

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        decoded = _decode_dicts_best_effort(line)
        if decoded:
            rows.extend(decoded)
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
