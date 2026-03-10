from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeProcessEvent,
)
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
if TYPE_CHECKING:
    from server.runtime.adapter.common.profile_loader import ProcessItemMappingProfile
    from .execution_adapter import CodexExecutionAdapter


def _summarize(value: str, *, limit: int = 220) -> str:
    compact = " ".join(value.replace("\r", "\n").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


class CodexStreamParser:
    def __init__(self, adapter: "CodexExecutionAdapter") -> None:
        self._adapter = adapter

    def _slice_latest_turn_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not rows:
            return rows

        start_idx: int | None = None
        end_idx: int | None = None
        for idx, row in enumerate(rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            event_type = payload.get("type")
            if event_type == "turn.started":
                start_idx = idx
            elif event_type == "turn.completed" and start_idx is not None:
                end_idx = idx

        if start_idx is None:
            return rows
        if end_idx is not None and end_idx >= start_idx:
            return rows[start_idx : end_idx + 1]
        return rows[start_idx:]

    def _process_extract_profile(self) -> tuple[set[str], set[str], dict[str, "ProcessItemMappingProfile"]]:
        profile_obj = getattr(self._adapter, "profile", None)
        profile = getattr(profile_obj, "parser_process_extract", None)
        if profile is None:
            return {"turn.started"}, {"turn.completed"}, {}
        turn_start_types = {
            item.strip()
            for item in profile.turn_start_payload_types
            if isinstance(item, str) and item.strip()
        }
        turn_end_types = {
            item.strip()
            for item in profile.turn_end_payload_types
            if isinstance(item, str) and item.strip()
        }
        mapping_by_item: dict[str, ProcessItemMappingProfile] = {}
        for mapping in profile.item_type_mappings:
            key = mapping.item_type.strip()
            if key:
                mapping_by_item[key] = mapping
        return (
            turn_start_types or {"turn.started"},
            turn_end_types or {"turn.completed"},
            mapping_by_item,
        )

    def parse(self, raw_stdout: str) -> dict[str, object]:
        parsed_rows: list[dict[str, object]] = []
        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                parsed_rows.append({"payload": event})

        last_message_text = ""
        for row in self._slice_latest_turn_rows(parsed_rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "agent_message":
                continue
            text = item.get("text")
            if isinstance(text, str):
                last_message_text = text

        if not last_message_text:
            last_message_text = raw_stdout

        result, repair_level = self._adapter._parse_json_with_deterministic_repair(last_message_text)  # noqa: SLF001
        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {
                "turn_result": turn_result.model_dump(),
                "structured_payload": structured_payload,
            }
        turn_result = self._adapter._turn_error(message="failed to parse codex output")  # noqa: SLF001
        return {
            "turn_result": turn_result.model_dump(),
            "structured_payload": None,
        }

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> dict[str, object]:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        records_all, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records_all, pty_raw_rows = collect_json_parse_errors(pty_rows)
        records = self._slice_latest_turn_rows(records_all)
        pty_records = self._slice_latest_turn_rows(pty_records_all)

        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        turn_completed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_start_seen = False
        turn_start_raw_ref: dict[str, Any] | None = None
        turn_complete_raw_ref: dict[str, Any] | None = None
        run_handle_id: str | None = None
        run_handle_raw_ref: dict[str, Any] | None = None
        turn_start_types, turn_end_types, process_mapping_by_item = self._process_extract_profile()

        def _extract_run_handle(rows: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("type") or "") != "thread.started":
                    continue
                session_candidate = find_session_id(payload)
                if isinstance(session_candidate, str) and session_candidate.strip():
                    return (
                        session_candidate.strip(),
                        {
                            "stream": str(row.get("stream") or "stdout"),
                            "byte_from": int(row.get("byte_from") or 0),
                            "byte_to": int(row.get("byte_to") or 0),
                        },
                    )
            return None, None

        run_handle_id, run_handle_raw_ref = _extract_run_handle(cast(list[dict[str, Any]], records_all))
        if run_handle_id is None:
            run_handle_id, run_handle_raw_ref = _extract_run_handle(cast(list[dict[str, Any]], pty_records_all))

        def _collect(rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_completed, turn_complete_data, turn_start_seen, turn_start_raw_ref, turn_complete_raw_ref
            for row in rows:
                payload = row["payload"]
                if not isinstance(payload, dict):
                    continue
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type_obj = payload.get("type")
                payload_type = payload_type_obj if isinstance(payload_type_obj, str) else None
                if payload_type:
                    structured_types.append(payload_type)
                    if payload_type in turn_start_types and not turn_start_seen:
                        turn_start_seen = True
                        turn_start_raw_ref = {
                            "stream": str(row["stream"]),
                            "byte_from": row["byte_from"] if isinstance(row["byte_from"], int) else 0,
                            "byte_to": row["byte_to"] if isinstance(row["byte_to"], int) else 0,
                        }
                    if payload_type in turn_end_types:
                        turn_completed = True
                        turn_complete_raw_ref = {
                            "stream": str(row["stream"]),
                            "byte_from": row["byte_from"] if isinstance(row["byte_from"], int) else 0,
                            "byte_to": row["byte_to"] if isinstance(row["byte_to"], int) else 0,
                        }
                        usage_obj = payload.get("usage")
                        if isinstance(usage_obj, dict):
                            turn_complete_data = dict(usage_obj)

                item = payload.get("item")
                if not isinstance(item, dict):
                    continue
                item_type_obj = item.get("type")
                item_type = item_type_obj if isinstance(item_type_obj, str) else None
                if not item_type:
                    continue

                if payload_type == "item.completed" and item_type == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        row_stream = str(row["stream"])
                        row_from = row["byte_from"]
                        row_to = row["byte_to"]
                        item_id = item.get("id")
                        message_id = item_id if isinstance(item_id, str) and item_id.strip() else None
                        assistant_message: RuntimeAssistantMessage = {
                            "text": text,
                            "raw_ref": {
                                "stream": row_stream,
                                "byte_from": row_from if isinstance(row_from, int) else 0,
                                "byte_to": row_to if isinstance(row_to, int) else 0,
                            },
                        }
                        if isinstance(message_id, str):
                            assistant_message["message_id"] = message_id
                        assistant_messages.append(assistant_message)
                    continue

                mapping = process_mapping_by_item.get(item_type)
                if mapping is None or payload_type != "item.completed":
                    continue
                row_stream = str(row["stream"])
                row_from = row["byte_from"]
                row_to = row["byte_to"]
                item_id_obj = item.get("id")
                message_id = (
                    item_id_obj
                    if isinstance(item_id_obj, str) and item_id_obj.strip()
                    else f"{item_type}_{row_from if isinstance(row_from, int) else 0}"
                )
                summary_value = item.get(mapping.summary_field) if mapping.summary_field else None
                if isinstance(summary_value, str) and summary_value.strip():
                    summary = _summarize(summary_value)
                else:
                    summary = f"{item_type} completed"
                text_obj = item.get(mapping.text_field) if mapping.text_field else None
                text_value: str | None = None
                if isinstance(text_obj, str) and text_obj.strip():
                    text_value = text_obj
                elif text_obj is not None:
                    text_value = json.dumps(text_obj, ensure_ascii=False)
                details: dict[str, Any] = {
                    "item_type": item_type,
                    "payload_type": payload_type,
                }
                for key in ("command", "status", "exit_code", "name"):
                    value = item.get(key)
                    if value is not None:
                        details[key] = value
                if "arguments" in item and item.get("arguments") is not None:
                    details["arguments"] = item.get("arguments")
                process_events.append(
                    {
                        "process_type": mapping.process_type,
                        "message_id": message_id,
                        "summary": summary,
                        "classification": mapping.classification or mapping.process_type,
                        "details": details,
                        "text": text_value,
                        "raw_ref": {
                            "stream": row_stream,
                            "byte_from": row_from if isinstance(row_from, int) else 0,
                            "byte_to": row_to if isinstance(row_to, int) else 0,
                        },
                    }
                )

        _collect(cast(list[dict[str, Any]], records))

        stdout_turn_completed = any(
            isinstance(row["payload"], dict) and str(row["payload"].get("type") or "") in turn_end_types
            for row in records
        )
        pty_turn_completed = any(
            isinstance(row["payload"], dict) and str(row["payload"].get("type") or "") in turn_end_types
            for row in pty_records
        )
        use_pty_fallback = (not assistant_messages and pty_records) or (
            not stdout_turn_completed and pty_turn_completed
        )

        if use_pty_fallback:
            diagnostics.append("PTY_FALLBACK_USED")
            _collect(cast(list[dict[str, Any]], pty_records))

        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        auth_signal = detect_auth_signal_from_patterns(
            engine="codex",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "codex",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": "\n".join(
                    part for part in (stdout_text, stderr_text, pty_text) if part
                ),
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "extracted": {},
            },
        )

        turn_markers: list[dict[str, Any]] = []
        if turn_start_seen:
            turn_markers.append({"marker": "start", "raw_ref": turn_start_raw_ref})
        if turn_completed:
            marker_payload: dict[str, Any] = {"marker": "complete", "raw_ref": turn_complete_raw_ref}
            if isinstance(turn_complete_data, dict):
                marker_payload["data"] = turn_complete_data
            turn_markers.append(marker_payload)

        result: dict[str, object] = {
            "parser": "codex_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "process_events": process_events,
            "turn_started": turn_start_seen,
            "turn_completed": turn_completed,
            "turn_markers": turn_markers,
            "raw_rows": list(raw_rows),
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
        if isinstance(turn_complete_data, dict):
            result["turn_complete_data"] = turn_complete_data
        if isinstance(run_handle_id, str) and run_handle_id.strip():
            result["run_handle"] = {
                "handle_id": run_handle_id.strip(),
                "raw_ref": run_handle_raw_ref,
            }
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_CodexLiveSession":
        return _CodexLiveSession(self)


class _CodexLiveSession:
    def __init__(self, parser: CodexStreamParser) -> None:
        self._parser = parser
        self._buffers: dict[str, str] = {"stdout": "", "pty": ""}
        self._buffer_byte_start: dict[str, int] = {"stdout": 0, "pty": 0}
        (
            self._turn_start_types,
            self._turn_end_types,
            self._process_mapping_by_item,
        ) = self._parser._process_extract_profile()  # noqa: SLF001
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._run_handle_emitted = False

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        if stream not in {"stdout", "pty"}:
            return []
        previous_tail = self._buffers.get(stream, "")
        previous_tail_start = self._buffer_byte_start.get(stream, int(byte_from))
        if previous_tail:
            combined = f"{previous_tail}{text}"
            combined_start = previous_tail_start
        else:
            combined = text
            combined_start = int(byte_from)
        if "\n" not in combined:
            self._buffers[stream] = combined
            self._buffer_byte_start[stream] = combined_start
            return []
        lines = combined.splitlines(keepends=True)
        complete = lines[:-1]
        tail = lines[-1]
        if tail.endswith("\n"):
            complete.append(tail)
            tail = ""
        self._buffers[stream] = tail
        cursor = combined_start
        self._buffer_byte_start[stream] = cursor
        emissions: list[LiveParserEmission] = []
        for line in complete:
            clean = line.strip()
            encoded = line.encode("utf-8", errors="replace")
            row_from = cursor
            row_to = cursor + len(encoded)
            cursor = row_to
            self._buffer_byte_start[stream] = cursor
            if not clean:
                continue
            try:
                payload = json.loads(clean)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            payload_type_obj = payload.get("type")
            payload_type = payload_type_obj if isinstance(payload_type_obj, str) else None
            session_id = find_session_id(payload)
            if (
                payload_type == "thread.started"
                and not self._run_handle_emitted
                and isinstance(session_id, str)
                and session_id.strip()
            ):
                self._run_handle_emitted = True
                emissions.append(
                    {
                        "kind": "run_handle",
                        "handle_id": session_id.strip(),
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": row_from,
                            "byte_to": row_to,
                        },
                    }
                )
            if payload_type and payload_type in self._turn_start_types and not self._turn_start_emitted:
                self._turn_start_emitted = True
                emissions.append(
                    {
                        "kind": "turn_marker",
                        "marker": "start",
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": row_from,
                            "byte_to": row_to,
                        },
                    }
                )
            if payload_type and payload_type in self._turn_end_types and not self._turn_complete_emitted:
                self._turn_complete_emitted = True
                turn_complete_data_obj = payload.get("usage")
                turn_complete_data = (
                    dict(turn_complete_data_obj)
                    if isinstance(turn_complete_data_obj, dict)
                    else None
                )
                marker_emission: LiveParserEmission = {
                    "kind": "turn_marker",
                    "marker": "complete",
                    "raw_ref": {
                        "stream": stream,
                        "byte_from": row_from,
                        "byte_to": row_to,
                    },
                }
                if isinstance(turn_complete_data, dict):
                    marker_emission["turn_complete_data"] = turn_complete_data
                emissions.append(marker_emission)
                completion_emission: LiveParserEmission = {"kind": "turn_completed"}
                if isinstance(turn_complete_data, dict):
                    completion_emission["turn_complete_data"] = turn_complete_data
                emissions.append(completion_emission)

            item = payload.get("item")
            if not isinstance(item, dict):
                continue
            item_type_obj = item.get("type")
            item_type = item_type_obj if isinstance(item_type_obj, str) else None
            if not item_type:
                continue

            if payload_type == "item.completed" and item_type == "agent_message":
                text_obj = item.get("text")
                if not isinstance(text_obj, str) or not text_obj.strip():
                    continue
                emission: LiveParserEmission = {
                    "kind": "assistant_message",
                    "text": text_obj,
                    "raw_ref": {
                        "stream": stream,
                        "byte_from": row_from,
                        "byte_to": row_to,
                    },
                }
                item_id = item.get("id")
                if isinstance(item_id, str) and item_id.strip():
                    emission["message_id"] = item_id
                if session_id:
                    emission["session_id"] = session_id
                emissions.append(emission)
                continue

            mapping = self._process_mapping_by_item.get(item_type)
            if mapping is None or payload_type != "item.completed":
                continue
            summary_obj = item.get(mapping.summary_field) if mapping.summary_field else None
            if isinstance(summary_obj, str) and summary_obj.strip():
                summary = _summarize(summary_obj)
            else:
                summary = f"{item_type} completed"
            text_obj = item.get(mapping.text_field) if mapping.text_field else None
            text_value: str | None = None
            if isinstance(text_obj, str) and text_obj.strip():
                text_value = text_obj
            elif text_obj is not None:
                text_value = json.dumps(text_obj, ensure_ascii=False)
            details: dict[str, Any] = {
                "item_type": item_type,
                "payload_type": payload_type,
            }
            for key in ("command", "status", "exit_code", "name"):
                value = item.get(key)
                if value is not None:
                    details[key] = value
            if "arguments" in item and item.get("arguments") is not None:
                details["arguments"] = item.get("arguments")
            process_emission: LiveParserEmission = {
                "kind": "process_event",
                "process_type": mapping.process_type,
                "summary": summary,
                "classification": mapping.classification or mapping.process_type,
                "details": details,
                "raw_ref": {
                    "stream": stream,
                    "byte_from": row_from,
                    "byte_to": row_to,
                },
            }
            item_id = item.get("id")
            if isinstance(item_id, str) and item_id.strip():
                process_emission["message_id"] = item_id
            if isinstance(text_value, str) and text_value:
                process_emission["text"] = text_value
            if session_id:
                process_emission["session_id"] = session_id
            emissions.append(process_emission)
        return emissions

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        return []
