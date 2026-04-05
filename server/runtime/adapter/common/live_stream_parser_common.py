from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Literal

from server.runtime.adapter.types import LiveParserEmission, RuntimeStreamRawRef
from server.runtime.protocol.contracts import LiveStreamParserSession

LIVE_STREAM_LINE_LIMIT_BYTES = 4096
LIVE_STREAM_LINE_TRUNCATION_MARKER = " ... [truncated by live overflow guard]"
LIVE_STREAM_LINE_OVERFLOW_REPAIRED = "RUNTIME_STREAM_LINE_OVERFLOW_REPAIRED"
LIVE_STREAM_LINE_OVERFLOW_UNREPAIRABLE = "RUNTIME_STREAM_LINE_OVERFLOW_UNREPAIRABLE"
RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED = "RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED"
RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED = (
    "RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED"
)
SemanticOverflowExemptionKind = Literal["reasoning", "assistant_message"]
NdjsonOverflowExemptionProbe = Callable[[str, str], SemanticOverflowExemptionKind | None]


@dataclass
class _JsonContext:
    kind: str
    state: str


@dataclass
class _LineState:
    start_byte: int | None = None
    total_bytes: int = 0
    prefix_text: str = ""
    prefix_bytes: int = 0
    overflowed: bool = False
    exemption_kind: SemanticOverflowExemptionKind | None = None


@dataclass
class PreparedNdjsonLine:
    text: str
    byte_from: int
    byte_to: int
    repaired: bool = False
    repair_failed: bool = False
    diagnostic_details: dict[str, Any] | None = None


@dataclass
class SanitizedIngressChunk:
    text: str
    byte_from: int
    byte_to: int
    diagnostics: list[LiveParserEmission]


def parse_repaired_ndjson_dict(line_text: str) -> dict[str, Any] | None:
    candidate = repair_truncated_json_line(line_text.rstrip("\n"))
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def resolve_ndjson_overflow_exemption_probe(stream_parser: Any) -> NdjsonOverflowExemptionProbe | None:
    probe = getattr(stream_parser, "classify_ndjson_overflow_exemption", None)
    if callable(probe):
        return probe
    return None


def _truncate_text_to_byte_limit(text: str, limit_bytes: int) -> str:
    if limit_bytes <= 0 or not text:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit_bytes:
        return text
    truncated = encoded[:limit_bytes]
    return truncated.decode("utf-8", errors="ignore")


def _append_retained_segment(
    *,
    state: _LineState,
    segment: str,
    segment_bytes: int,
) -> None:
    state.prefix_text = f"{state.prefix_text}{segment}"
    state.prefix_bytes += segment_bytes


def _classify_overflow_exemption(
    *,
    probe: NdjsonOverflowExemptionProbe | None,
    stream: str,
    line_text: str,
) -> SemanticOverflowExemptionKind | None:
    if probe is None:
        return None
    return probe(stream, line_text)


def _append_ndjson_segment_with_limit(
    *,
    state: _LineState,
    stream: str,
    segment: str,
    limit_bytes: int,
    exemption_probe: NdjsonOverflowExemptionProbe | None,
) -> None:
    if state.overflowed or not segment:
        return
    segment_bytes = len(segment.encode("utf-8", errors="replace"))
    if state.exemption_kind is not None:
        _append_retained_segment(
            state=state,
            segment=segment,
            segment_bytes=segment_bytes,
        )
        return
    exemption_kind = _classify_overflow_exemption(
        probe=exemption_probe,
        stream=stream,
        line_text=f"{state.prefix_text}{segment}",
    )
    if exemption_kind is not None:
        state.exemption_kind = exemption_kind
        _append_retained_segment(
            state=state,
            segment=segment,
            segment_bytes=segment_bytes,
        )
        return
    remaining = limit_bytes - state.prefix_bytes
    if remaining > 0:
        kept = _truncate_text_to_byte_limit(segment, remaining)
        if kept:
            state.prefix_text = f"{state.prefix_text}{kept}"
            state.prefix_bytes += len(kept.encode("utf-8", errors="replace"))
    if state.prefix_bytes >= limit_bytes:
        state.overflowed = True


def _append_closing_value(parts: list[str], *, ctx: _JsonContext) -> None:
    if ctx.kind == "object":
        if ctx.state == "colon":
            parts.append(": null")
        elif ctx.state == "value":
            parts.append("null")
    elif ctx.kind == "array" and ctx.state == "value_or_end":
        parts.append("null")


def _mark_parent_value_complete(stack: list[_JsonContext]) -> None:
    if not stack:
        return
    parent = stack[-1]
    if parent.kind == "object" and parent.state == "value_container":
        parent.state = "comma_or_end"
    elif parent.kind == "array" and parent.state == "value_container":
        parent.state = "comma_or_end"


def _scan_json_prefix(prefix: str) -> tuple[list[_JsonContext], bool, bool]:
    stack: list[_JsonContext] = []
    in_string = False
    escape = False

    for ch in prefix:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
                if stack:
                    current = stack[-1]
                    if current.kind == "object":
                        if current.state == "key_string":
                            current.state = "colon"
                        elif current.state == "value_string":
                            current.state = "comma_or_end"
                    elif current.kind == "array" and current.state == "value_string":
                        current.state = "comma_or_end"
                continue
            continue

        if ch.isspace():
            continue
        context: _JsonContext | None = stack[-1] if stack else None
        if context is None:
            if ch == "{":
                stack.append(_JsonContext(kind="object", state="key_or_end"))
            elif ch == "[":
                stack.append(_JsonContext(kind="array", state="value_or_end"))
            elif ch == '"':
                in_string = True
            continue

        if context.kind == "object":
            if context.state == "key_or_end":
                if ch == "}":
                    stack.pop()
                    _mark_parent_value_complete(stack)
                elif ch == '"':
                    context.state = "key_string"
                    in_string = True
            elif context.state == "colon":
                if ch == ":":
                    context.state = "value"
            elif context.state == "value":
                if ch == "{":
                    context.state = "value_container"
                    stack.append(_JsonContext(kind="object", state="key_or_end"))
                elif ch == "[":
                    context.state = "value_container"
                    stack.append(_JsonContext(kind="array", state="value_or_end"))
                elif ch == '"':
                    context.state = "value_string"
                    in_string = True
                else:
                    context.state = "value_primitive"
            elif context.state == "value_primitive":
                if ch == ",":
                    context.state = "key_or_end"
                elif ch == "}":
                    stack.pop()
                    _mark_parent_value_complete(stack)
            elif context.state == "comma_or_end":
                if ch == ",":
                    context.state = "key_or_end"
                elif ch == "}":
                    stack.pop()
                    _mark_parent_value_complete(stack)
        else:
            if context.state == "value_or_end":
                if ch == "]":
                    stack.pop()
                    _mark_parent_value_complete(stack)
                elif ch == "{":
                    context.state = "value_container"
                    stack.append(_JsonContext(kind="object", state="key_or_end"))
                elif ch == "[":
                    context.state = "value_container"
                    stack.append(_JsonContext(kind="array", state="value_or_end"))
                elif ch == '"':
                    context.state = "value_string"
                    in_string = True
                else:
                    context.state = "value_primitive"
            elif context.state == "value_primitive":
                if ch == ",":
                    context.state = "value_or_end"
                elif ch == "]":
                    stack.pop()
                    _mark_parent_value_complete(stack)
            elif context.state == "comma_or_end":
                if ch == ",":
                    context.state = "value_or_end"
                elif ch == "]":
                    stack.pop()
                    _mark_parent_value_complete(stack)

    return stack, in_string, escape


def repair_truncated_json_line(prefix: str) -> str | None:
    base = prefix.rstrip("\r\n")
    if not base.strip():
        return None
    try:
        payload = json.loads(base)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        return base

    max_trim = min(len(base), 256)
    for trim in range(0, max_trim + 1):
        candidate = base[:-trim] if trim else base
        if not candidate.strip():
            break
        stack, in_string, escape = _scan_json_prefix(candidate)
        working = candidate
        if in_string:
            if escape and working.endswith("\\"):
                working = working[:-1]
            working = f"{working}{LIVE_STREAM_LINE_TRUNCATION_MARKER}\""
            stack, in_string, escape = _scan_json_prefix(working)
        if in_string or escape:
            continue

        suffix: list[str] = []
        for ctx in reversed(stack):
            _append_closing_value(suffix, ctx=ctx)
            suffix.append("}" if ctx.kind == "object" else "]")
        synthesized = f"{working}{''.join(suffix)}"
        try:
            payload = json.loads(synthesized)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return synthesized
    return None


def repair_truncated_json_line_with_limit(prefix: str, *, output_limit_bytes: int) -> str | None:
    if output_limit_bytes <= 0:
        return None
    candidate_limit = min(len(prefix.encode("utf-8", errors="replace")), output_limit_bytes)
    while candidate_limit > 0:
        candidate = _truncate_text_to_byte_limit(prefix, candidate_limit)
        repaired = repair_truncated_json_line(candidate)
        if repaired is not None and len(repaired.encode("utf-8", errors="replace")) <= output_limit_bytes:
            return repaired
        candidate_limit -= 128
    return None


def build_runtime_overflow_diagnostic_row(
    *,
    stream: str,
    limit_bytes: int,
    line_start_byte: int,
) -> str:
    return json.dumps(
        {
            "type": "runtime_diagnostic",
            "subtype": "ndjson_line_overflow_substituted",
            "stream": stream,
            "code": RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED,
            "threshold_bytes": limit_bytes,
            "line_start_byte": line_start_byte,
            "sanitized": True,
            "original_line_dropped": True,
        },
        ensure_ascii=False,
    )


class NdjsonIngressSanitizer:
    def __init__(
        self,
        *,
        accepted_streams: set[str],
        limit_bytes: int = LIVE_STREAM_LINE_LIMIT_BYTES,
        overflow_exemption_probe: NdjsonOverflowExemptionProbe | None = None,
    ) -> None:
        self._accepted_streams = set(accepted_streams)
        self._limit_bytes = max(1, int(limit_bytes))
        self._overflow_exemption_probe = overflow_exemption_probe
        self._states: dict[str, _LineState] = {
            stream: _LineState() for stream in self._accepted_streams
        }
        self._output_offsets: dict[str, int] = {stream: 0 for stream in self._accepted_streams}

    def feed(self, *, stream: str, text: str) -> list[SanitizedIngressChunk]:
        if stream not in self._accepted_streams or not text:
            return []
        state = self._states.setdefault(stream, _LineState())
        results: list[SanitizedIngressChunk] = []
        index = 0
        text_len = len(text)
        while index < text_len:
            newline_index = text.find("\n", index)
            if newline_index == -1:
                segment = text[index:]
                has_newline = False
                index = text_len
            else:
                segment = text[index : newline_index + 1]
                has_newline = True
                index = newline_index + 1
            self._append_segment(stream=stream, state=state, segment=segment)
            if has_newline:
                finalized = self._finalize_line(stream=stream, include_newline=True)
                if finalized is not None:
                    results.append(finalized)
                state = self._states.setdefault(stream, _LineState())
        return results

    def flush(self, *, stream: str) -> SanitizedIngressChunk | None:
        if stream not in self._accepted_streams:
            return None
        state = self._states.get(stream)
        if state is None or state.start_byte is None or state.total_bytes <= 0:
            return None
        return self._finalize_line(stream=stream, include_newline=False)

    def _append_segment(self, *, stream: str, state: _LineState, segment: str) -> None:
        segment_bytes = len(segment.encode("utf-8", errors="replace"))
        if state.start_byte is None:
            state.start_byte = state.total_bytes
        state.total_bytes += segment_bytes
        _append_ndjson_segment_with_limit(
            state=state,
            stream=stream,
            segment=segment,
            limit_bytes=self._limit_bytes,
            exemption_probe=self._overflow_exemption_probe,
        )

    def _finalize_line(self, *, stream: str, include_newline: bool) -> SanitizedIngressChunk | None:
        state = self._states.get(stream)
        if state is None or state.total_bytes <= 0:
            return None
        line_start = self._output_offsets.get(stream, 0)
        diagnostics: list[LiveParserEmission] = []
        if not state.overflowed or state.exemption_kind is not None:
            body = state.prefix_text.rstrip("\n")
        else:
            detail_payload = {
                "stream": stream,
                "threshold_bytes": self._limit_bytes,
                "line_start_byte": line_start,
                "sanitized": True,
                "original_line_dropped": True,
            }
            output_limit = self._limit_bytes - (1 if include_newline else 0)
            repaired = repair_truncated_json_line_with_limit(
                state.prefix_text.rstrip("\n"),
                output_limit_bytes=output_limit,
            )
            if repaired is None:
                body = build_runtime_overflow_diagnostic_row(
                    stream=stream,
                    limit_bytes=self._limit_bytes,
                    line_start_byte=line_start,
                )
                diagnostics.append(
                    {
                        "kind": "diagnostic",
                        "code": RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED,
                        "details": dict(detail_payload),
                    }
                )
            else:
                body = repaired
                diagnostics.append(
                    {
                        "kind": "diagnostic",
                        "code": RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED,
                        "details": dict(detail_payload),
                    }
                )
        text = f"{body}\n" if include_newline else body
        byte_length = len(text.encode("utf-8", errors="replace"))
        byte_from = line_start
        byte_to = line_start + byte_length
        raw_ref: RuntimeStreamRawRef = {"stream": stream, "byte_from": byte_from, "byte_to": byte_to}
        for diagnostic in diagnostics:
            diagnostic["raw_ref"] = raw_ref
        self._states[stream] = _LineState()
        self._output_offsets[stream] = byte_to
        return SanitizedIngressChunk(
            text=text,
            byte_from=byte_from,
            byte_to=byte_to,
            diagnostics=diagnostics,
        )


class NdjsonLineBuffer:
    def __init__(
        self,
        *,
        accepted_streams: set[str],
        limit_bytes: int = LIVE_STREAM_LINE_LIMIT_BYTES,
        overflow_exemption_probe: NdjsonOverflowExemptionProbe | None = None,
    ) -> None:
        self._accepted_streams = set(accepted_streams)
        self._limit_bytes = max(1, int(limit_bytes))
        self._overflow_exemption_probe = overflow_exemption_probe
        self._states: dict[str, _LineState] = {
            stream: _LineState() for stream in self._accepted_streams
        }

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[PreparedNdjsonLine]:
        if stream not in self._accepted_streams:
            return []
        state = self._states.setdefault(stream, _LineState())
        if not text:
            return []

        results: list[PreparedNdjsonLine] = []
        cursor = int(byte_from)
        index = 0
        text_len = len(text)
        while index < text_len:
            newline_index = text.find("\n", index)
            if newline_index == -1:
                segment = text[index:]
                has_newline = False
                index = text_len
            else:
                segment = text[index : newline_index + 1]
                has_newline = True
                index = newline_index + 1

            segment_bytes = len(segment.encode("utf-8", errors="replace"))
            segment_start = cursor
            cursor += segment_bytes
            if state.start_byte is None:
                state.start_byte = segment_start
            state.total_bytes += segment_bytes
            _append_ndjson_segment_with_limit(
                state=state,
                stream=stream,
                segment=segment,
                limit_bytes=self._limit_bytes,
                exemption_probe=self._overflow_exemption_probe,
            )

            if has_newline:
                prepared = self._finalize_state(state)
                if prepared is not None:
                    results.append(prepared)
                self._states[stream] = _LineState()
                state = self._states[stream]

        _ = byte_to
        return results

    def flush(self, *, stream: str) -> PreparedNdjsonLine | None:
        if stream not in self._accepted_streams:
            return None
        state = self._states.get(stream)
        if state is None or state.start_byte is None or state.total_bytes <= 0:
            return None
        prepared = self._finalize_state(state)
        self._states[stream] = _LineState()
        return prepared

    def _finalize_state(self, state: _LineState) -> PreparedNdjsonLine | None:
        if state.start_byte is None or state.total_bytes <= 0:
            return None
        raw_text = state.prefix_text.rstrip("\n")
        byte_from = state.start_byte
        byte_to = state.start_byte + state.total_bytes
        if not state.overflowed or state.exemption_kind is not None:
            return PreparedNdjsonLine(text=raw_text, byte_from=byte_from, byte_to=byte_to)

        details = {
            "stream_line_limit_bytes": self._limit_bytes,
            "line_start_byte": byte_from,
            "line_end_byte": byte_to,
            "reason": "line_exceeded_live_parser_limit",
        }
        repaired = repair_truncated_json_line(raw_text)
        if repaired is None:
            return PreparedNdjsonLine(
                text="",
                byte_from=byte_from,
                byte_to=byte_to,
                repair_failed=True,
                diagnostic_details=details,
            )
        return PreparedNdjsonLine(
            text=repaired,
            byte_from=byte_from,
            byte_to=byte_to,
            repaired=True,
            diagnostic_details=details,
        )


class NdjsonLiveStreamParserSession(LiveStreamParserSession, ABC):
    def __init__(
        self,
        *,
        accepted_streams: set[str] | None = None,
        overflow_exemption_probe: NdjsonOverflowExemptionProbe | None = None,
    ) -> None:
        self._accepted_streams = set(accepted_streams or {"stdout", "pty"})
        self._line_buffer = NdjsonLineBuffer(
            accepted_streams=self._accepted_streams,
            overflow_exemption_probe=overflow_exemption_probe,
        )

    @abstractmethod
    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        raise NotImplementedError

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        emissions: list[LiveParserEmission] = []
        for stream in sorted(self._accepted_streams):
            prepared = self._line_buffer.flush(stream=stream)
            if prepared is None:
                continue
            emissions.extend(self._process_prepared_line(stream=stream, line=prepared))
        return emissions

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        emissions: list[LiveParserEmission] = []
        for line in self._line_buffer.feed(
            stream=stream,
            text=text,
            byte_from=byte_from,
            byte_to=byte_to,
        ):
            emissions.extend(self._process_prepared_line(stream=stream, line=line))
        return emissions

    def _process_prepared_line(
        self,
        *,
        stream: str,
        line: PreparedNdjsonLine,
    ) -> list[LiveParserEmission]:
        emissions: list[LiveParserEmission] = []
        raw_ref: RuntimeStreamRawRef = {
            "stream": stream,
            "byte_from": line.byte_from,
            "byte_to": line.byte_to,
        }
        if line.repaired:
            emissions.append(
                {
                    "kind": "diagnostic",
                    "code": LIVE_STREAM_LINE_OVERFLOW_REPAIRED,
                    "details": dict(line.diagnostic_details or {}),
                    "raw_ref": raw_ref,
                }
            )
        elif line.repair_failed:
            emissions.append(
                {
                    "kind": "diagnostic",
                    "code": LIVE_STREAM_LINE_OVERFLOW_UNREPAIRABLE,
                    "details": dict(line.diagnostic_details or {}),
                    "raw_ref": raw_ref,
                }
            )
            return emissions
        clean = line.text.strip()
        if not clean:
            return emissions
        try:
            payload = json.loads(clean)
        except json.JSONDecodeError:
            return emissions
        if not isinstance(payload, dict):
            return emissions
        emissions.extend(
            self.handle_live_row(
                payload=payload,
                raw_ref=raw_ref,
                stream=stream,
            )
        )
        return emissions
