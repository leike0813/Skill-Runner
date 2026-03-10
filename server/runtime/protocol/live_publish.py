from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Set, cast

from server.models import (
    ConversationEventEnvelope,
    FcmpEventType,
    RuntimeEventCategory,
    RuntimeEventEnvelope,
    RuntimeEventIdentity,
    RuntimeEventRef,
    RuntimeEventSource,
)
from server.runtime.chat_replay.publisher import chat_replay_publisher
from server.runtime.adapter.types import LiveParserEmission, RuntimeStreamRawRef
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.observability.rasp_live_journal import rasp_live_journal
from server.runtime.adapter.types import RuntimeStreamRawRow

from .contracts import LiveRuntimeEmitter, LiveStreamParserSession
from .factories import make_fcmp_event, make_rasp_event
from .final_promotion_coordinator import (
    FinalPromotionCoordinator,
    build_process_payload,
)
from .ordering_gate import OrderingPrerequisite, RuntimeEventCandidate, RuntimeEventOrderingGate
from .rasp_canonicalizer import coalesce_rasp_raw_rows
from .schema_registry import validate_fcmp_event, validate_rasp_event

logger = logging.getLogger(__name__)


def _read_jsonl(path: Path) -> List[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: List[dict[str, Any]] = []
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

    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                text = line.strip()
                if not text:
                    continue
                decoded = _decode_dicts_best_effort(text)
                if decoded:
                    rows.extend(decoded)
    except OSError:
        return []
    return rows


def _append_jsonl_sync(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False))
        fp.write("\n")


class FcmpAuditMirrorWriter:
    def __init__(self) -> None:
        self._pending_tasks_by_run: dict[str, Set[asyncio.Task[Any]]] = defaultdict(set)
        self._path_locks: dict[str, asyncio.Lock] = {}

    def _lock_for_path(self, path: Path) -> asyncio.Lock:
        key = str(path.resolve(strict=False))
        lock = self._path_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._path_locks[key] = lock
        return lock

    async def append_row(self, *, run_dir: Path, attempt_number: int, row: dict[str, Any]) -> None:
        path = run_dir / ".audit" / f"fcmp_events.{attempt_number}.jsonl"
        lock = self._lock_for_path(path)
        async with lock:
            _append_jsonl_sync(path, row)

    def enqueue(self, *, run_dir: Path, attempt_number: int, row: dict[str, Any]) -> None:
        run_id_obj = row.get("run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else run_dir.name
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _append_jsonl_sync(run_dir / ".audit" / f"fcmp_events.{attempt_number}.jsonl", row)
            return
        task = loop.create_task(self.append_row(run_dir=run_dir, attempt_number=attempt_number, row=row))
        pending = self._pending_tasks_by_run[run_id]
        pending.add(task)

        def _on_done(done_task: asyncio.Task[Any]) -> None:
            task_set = self._pending_tasks_by_run.get(run_id)
            if task_set is None:
                return
            task_set.discard(done_task)
            if not task_set:
                self._pending_tasks_by_run.pop(run_id, None)

        task.add_done_callback(_on_done)

    async def drain(self, *, run_id: Optional[str] = None) -> None:
        tasks: list[asyncio.Task[Any]] = []
        if run_id is None:
            for task_set in self._pending_tasks_by_run.values():
                tasks.extend(task_set)
        else:
            tasks.extend(self._pending_tasks_by_run.get(run_id, set()))
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)


class RaspAuditMirrorWriter:
    def __init__(self) -> None:
        self._pending_tasks_by_run: dict[str, Set[asyncio.Task[Any]]] = defaultdict(set)
        self._path_locks: dict[str, asyncio.Lock] = {}

    def _lock_for_path(self, path: Path) -> asyncio.Lock:
        key = str(path.resolve(strict=False))
        lock = self._path_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._path_locks[key] = lock
        return lock

    async def append_row(self, *, run_dir: Path, attempt_number: int, row: dict[str, Any]) -> None:
        path = run_dir / ".audit" / f"events.{attempt_number}.jsonl"
        lock = self._lock_for_path(path)
        async with lock:
            _append_jsonl_sync(path, row)

    def enqueue(self, *, run_dir: Path, attempt_number: int, row: dict[str, Any]) -> None:
        run_id_obj = row.get("run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else run_dir.name
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _append_jsonl_sync(run_dir / ".audit" / f"events.{attempt_number}.jsonl", row)
            return
        task = loop.create_task(self.append_row(run_dir=run_dir, attempt_number=attempt_number, row=row))
        pending = self._pending_tasks_by_run[run_id]
        pending.add(task)

        def _on_done(done_task: asyncio.Task[Any]) -> None:
            task_set = self._pending_tasks_by_run.get(run_id)
            if task_set is None:
                return
            task_set.discard(done_task)
            if not task_set:
                self._pending_tasks_by_run.pop(run_id, None)

        task.add_done_callback(_on_done)

    async def drain(self, *, run_id: Optional[str] = None) -> None:
        tasks: list[asyncio.Task[Any]] = []
        if run_id is None:
            for task_set in self._pending_tasks_by_run.values():
                tasks.extend(task_set)
        else:
            tasks.extend(self._pending_tasks_by_run.get(run_id, set()))
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)


class FcmpEventPublisher:
    def __init__(self, *, mirror_writer: FcmpAuditMirrorWriter | None = None) -> None:
        self._mirror_writer = mirror_writer or FcmpAuditMirrorWriter()
        self._next_seq_by_run: dict[str, int] = {}
        self._next_local_seq_by_run_attempt: dict[tuple[str, int], int] = {}
        self._gate_by_run: dict[str, RuntimeEventOrderingGate] = {}
        self._buffered_rows_by_run: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def _bootstrap_run(self, *, run_dir: Path, run_id: str) -> None:
        if run_id in self._next_seq_by_run:
            return
        audit_dir = run_dir / ".audit"
        max_global = 0
        local_seq_by_attempt: dict[int, int] = defaultdict(int)
        for path in sorted(audit_dir.glob("fcmp_events.*.jsonl")):
            for row in _read_jsonl(path):
                seq_obj = row.get("seq")
                if isinstance(seq_obj, int):
                    max_global = max(max_global, seq_obj)
                meta_obj = row.get("meta")
                if not isinstance(meta_obj, dict):
                    continue
                attempt_obj = meta_obj.get("attempt")
                local_seq_obj = meta_obj.get("local_seq")
                if isinstance(attempt_obj, int) and isinstance(local_seq_obj, int):
                    local_seq_by_attempt[attempt_obj] = max(local_seq_by_attempt[attempt_obj], local_seq_obj)
        self._next_seq_by_run[run_id] = max_global + 1
        for attempt_number, next_local in local_seq_by_attempt.items():
            self._next_local_seq_by_run_attempt[(run_id, attempt_number)] = next_local + 1

    def _gate_for_run(self, run_id: str) -> RuntimeEventOrderingGate:
        gate = self._gate_by_run.get(run_id)
        if gate is None:
            gate = RuntimeEventOrderingGate()
            self._gate_by_run[run_id] = gate
        return gate

    def _event_kind_for_row(self, row: dict[str, Any]) -> str:
        type_name = str(row.get("type") or "")
        if type_name == FcmpEventType.CONVERSATION_STATE_CHANGED.value:
            data_obj = row.get("data")
            data = data_obj if isinstance(data_obj, dict) else {}
            target_state = str(data.get("to") or "").strip()
            if target_state:
                return f"conversation.state.changed.{target_state}"
            return "conversation.state.changed"
        if type_name == FcmpEventType.USER_INPUT_REQUIRED.value:
            return "interaction.prompted"
        if type_name == FcmpEventType.AUTH_REQUIRED.value:
            data_obj = row.get("data")
            data = data_obj if isinstance(data_obj, dict) else {}
            phase = str(data.get("phase") or "").strip()
            if phase == "method_selection":
                return "auth.method.selection.required"
            return "auth.required"
        if type_name == FcmpEventType.AUTH_CHALLENGE_UPDATED.value:
            return "auth.challenge.updated"
        return type_name

    def _candidate_for_row(self, row: dict[str, Any]) -> RuntimeEventCandidate:
        meta_obj = row.get("meta")
        meta = meta_obj if isinstance(meta_obj, dict) else {}
        attempt_number = int(meta.get("attempt") or 1)
        correlation = dict(row.get("correlation") or {})
        publish_id = str(correlation["publish_id"])
        event_kind = self._event_kind_for_row(row)
        prerequisites: list[OrderingPrerequisite] = []
        if event_kind == "conversation.state.changed.succeeded":
            prerequisites.append(OrderingPrerequisite(event_kind="assistant.message.final"))
        elif event_kind == "conversation.state.changed.waiting_user":
            prerequisites.append(OrderingPrerequisite(event_kind="interaction.prompted"))
        elif event_kind == "auth.challenge.updated":
            data_obj = row.get("data")
            data = data_obj if isinstance(data_obj, dict) else {}
            auth_route = str(correlation.get("auth_route") or "").strip()
            available_methods = data.get("available_methods")
            if auth_route == "multi_method" or (
                isinstance(available_methods, list) and len(available_methods) > 1
            ):
                prerequisites.append(OrderingPrerequisite(event_kind="auth.method.selection.required"))
        return RuntimeEventCandidate(
            stream="fcmp",
            source_kind=(
                "parser"
                if event_kind in {
                    FcmpEventType.ASSISTANT_REASONING.value,
                    FcmpEventType.ASSISTANT_TOOL_CALL.value,
                    FcmpEventType.ASSISTANT_COMMAND_EXECUTION.value,
                    FcmpEventType.ASSISTANT_MESSAGE_PROMOTED.value,
                    FcmpEventType.ASSISTANT_MESSAGE_FINAL.value,
                    FcmpEventType.DIAGNOSTIC_WARNING.value,
                    FcmpEventType.RAW_STDOUT.value,
                    FcmpEventType.RAW_STDERR.value,
                }
                else "orchestration"
            ),
            event_kind=event_kind,
            run_id=str(row.get("run_id") or ""),
            attempt_number=attempt_number,
            publish_id=publish_id,
            caused_by_publish_id=str(correlation.get("caused_by", "") or "") or None,
            payload=row,
            prerequisites=prerequisites,
        )

    def _commit_row(self, *, run_dir: Path, row: dict[str, Any]) -> dict[str, Any]:
        run_id = str(row.get("run_id") or "")
        meta_obj = row.get("meta")
        meta = dict(meta_obj) if isinstance(meta_obj, dict) else {}
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise ValueError("FCMP publish requires run_id")
        attempt_number = int(meta.get("attempt") or 1)
        self._bootstrap_run(run_dir=run_dir, run_id=run_id)
        row["seq"] = self._next_seq_by_run[run_id]
        self._next_seq_by_run[run_id] += 1
        local_key = (run_id, attempt_number)
        local_seq = self._next_local_seq_by_run_attempt.get(local_key, 1)
        self._next_local_seq_by_run_attempt[local_key] = local_seq + 1
        meta["attempt"] = attempt_number
        meta["local_seq"] = local_seq
        correlation = dict(row.get("correlation") or {})
        correlation.setdefault("publish_id", uuid.uuid4().hex)
        row["meta"] = meta
        row["correlation"] = correlation
        validate_fcmp_event(row)
        is_terminal = False
        if str(row.get("type") or "") == FcmpEventType.CONVERSATION_STATE_CHANGED.value:
            data_obj = row.get("data")
            data = data_obj if isinstance(data_obj, dict) else {}
            target_state = str(data.get("to") or "")
            is_terminal = target_state in {"succeeded", "failed", "canceled"}
        published = fcmp_live_journal.publish(
            run_id=run_id,
            row=row,
            terminal=is_terminal,
        )
        self._mirror_writer.enqueue(run_dir=run_dir, attempt_number=attempt_number, row=published)
        chat_replay_publisher.publish_from_fcmp(run_dir=run_dir, row=published)
        return published

    def _release_ready(self, *, run_dir: Path, run_id: str) -> list[dict[str, Any]]:
        gate = self._gate_for_run(run_id)
        released_rows: list[dict[str, Any]] = []
        while True:
            released_candidates = gate.release_ready()
            if not released_candidates:
                break
            for candidate in released_candidates:
                buffered_row = self._buffered_rows_by_run[run_id].pop(candidate.publish_id, None)
                if buffered_row is None:
                    continue
                released_rows.append(self._commit_row(run_dir=run_dir, row=buffered_row))
        return released_rows

    def publish(self, *, run_dir: Path, event: ConversationEventEnvelope | dict[str, Any]) -> dict[str, Any]:
        row = event.model_dump(mode="json") if isinstance(event, ConversationEventEnvelope) else dict(event)
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise ValueError("FCMP publish requires run_id")
        correlation = dict(row.get("correlation") or {})
        correlation.setdefault("publish_id", uuid.uuid4().hex)
        row["correlation"] = correlation
        candidate = self._candidate_for_row(row)
        gate = self._gate_for_run(run_id)
        decision = gate.decide(candidate)
        if decision.kind == "buffer":
            self._buffered_rows_by_run[run_id][candidate.publish_id] = row
            return row
        published = self._commit_row(run_dir=run_dir, row=row)
        self._release_ready(run_dir=run_dir, run_id=run_id)
        return published

    async def drain_mirror(self, *, run_id: Optional[str] = None) -> None:
        drain = getattr(self._mirror_writer, "drain", None)
        if callable(drain):
            await drain(run_id=run_id)


class RaspEventPublisher:
    def __init__(self, *, mirror_writer: RaspAuditMirrorWriter | None = None) -> None:
        self._mirror_writer = mirror_writer or RaspAuditMirrorWriter()
        self._next_seq_by_run_attempt: dict[tuple[str, int], int] = {}
        self._gate_by_run: dict[str, RuntimeEventOrderingGate] = {}
        self._buffered_rows_by_run: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def _bootstrap_attempt(self, *, run_dir: Path, run_id: str, attempt_number: int) -> None:
        key = (run_id, attempt_number)
        if key in self._next_seq_by_run_attempt:
            return
        path = run_dir / ".audit" / f"events.{attempt_number}.jsonl"
        max_seq = 0
        for row in _read_jsonl(path):
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                max_seq = max(max_seq, seq_obj)
        self._next_seq_by_run_attempt[key] = max_seq + 1

    def _gate_for_run(self, run_id: str) -> RuntimeEventOrderingGate:
        gate = self._gate_by_run.get(run_id)
        if gate is None:
            gate = RuntimeEventOrderingGate()
            self._gate_by_run[run_id] = gate
        return gate

    def _candidate_for_row(self, row: dict[str, Any]) -> RuntimeEventCandidate:
        run_id = str(row.get("run_id") or "")
        attempt_number = int(row.get("attempt_number") or 1)
        correlation = dict(row.get("correlation") or {})
        publish_id = str(correlation["publish_id"])
        event_obj = row.get("event")
        event = event_obj if isinstance(event_obj, dict) else {}
        event_kind = str(event.get("type") or "rasp.unknown")
        return RuntimeEventCandidate(
            stream="rasp",
            source_kind="parser",
            event_kind=event_kind,
            run_id=run_id,
            attempt_number=attempt_number,
            publish_id=publish_id,
            caused_by_publish_id=str(correlation.get("caused_by", "") or "") or None,
            payload=row,
            prerequisites=[],
        )

    def _commit_row(self, *, run_dir: Path, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise ValueError("RASP publish requires run_id")
        attempt_number = int(row.get("attempt_number") or 1)
        self._bootstrap_attempt(run_dir=run_dir, run_id=run_id, attempt_number=attempt_number)
        key = (run_id, attempt_number)
        row["seq"] = self._next_seq_by_run_attempt[key]
        self._next_seq_by_run_attempt[key] += 1
        correlation = dict(row.get("correlation") or {})
        correlation.setdefault("publish_id", uuid.uuid4().hex)
        row["correlation"] = correlation
        validate_rasp_event(row)
        published = rasp_live_journal.publish(
            run_id=run_id,
            row=row,
            terminal=str((row.get("event") or {}).get("type") or "") == "lifecycle.run.terminal",
        )
        self._mirror_writer.enqueue(run_dir=run_dir, attempt_number=attempt_number, row=published)
        return published

    def _release_ready(self, *, run_dir: Path, run_id: str) -> list[dict[str, Any]]:
        gate = self._gate_for_run(run_id)
        released_rows: list[dict[str, Any]] = []
        while True:
            released_candidates = gate.release_ready()
            if not released_candidates:
                break
            for candidate in released_candidates:
                buffered_row = self._buffered_rows_by_run[run_id].pop(candidate.publish_id, None)
                if buffered_row is None:
                    continue
                released_rows.append(self._commit_row(run_dir=run_dir, row=buffered_row))
        return released_rows

    def publish(self, *, run_dir: Path, event: RuntimeEventEnvelope | dict[str, Any]) -> dict[str, Any]:
        row = event.model_dump(mode="json") if isinstance(event, RuntimeEventEnvelope) else dict(event)
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise ValueError("RASP publish requires run_id")
        correlation = dict(row.get("correlation") or {})
        correlation.setdefault("publish_id", uuid.uuid4().hex)
        row["correlation"] = correlation
        candidate = self._candidate_for_row(row)
        gate = self._gate_for_run(run_id)
        decision = gate.decide(candidate)
        if decision.kind == "buffer":
            self._buffered_rows_by_run[run_id][candidate.publish_id] = row
            return row
        published = self._commit_row(run_dir=run_dir, row=row)
        self._release_ready(run_dir=run_dir, run_id=run_id)
        return published

    async def drain_mirror(self, *, run_id: Optional[str] = None) -> None:
        drain = getattr(self._mirror_writer, "drain", None)
        if callable(drain):
            await drain(run_id=run_id)


class _BufferedLiveParserSession:
    def __init__(self, *, stream_parser: Any) -> None:
        self._stream_parser = stream_parser
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._pty = bytearray()

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        _ = byte_from
        _ = byte_to
        encoded = text.encode("utf-8", errors="replace")
        if stream == "stderr":
            self._stderr.extend(encoded)
        elif stream == "pty":
            self._pty.extend(encoded)
        else:
            self._stdout.extend(encoded)
        return []

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        parser = getattr(self._stream_parser, "parse_runtime_stream", None)
        if not callable(parser):
            return []
        parsed = parser(stdout_raw=bytes(self._stdout), stderr_raw=bytes(self._stderr), pty_raw=bytes(self._pty))
        emissions: list[LiveParserEmission] = []
        parsed_turn_complete_data = (
            parsed.get("turn_complete_data")
            if isinstance(parsed.get("turn_complete_data"), dict)
            else None
        )
        session_id = parsed.get("session_id")
        run_handle_obj = parsed.get("run_handle")
        if isinstance(run_handle_obj, dict):
            handle_id_obj = run_handle_obj.get("handle_id")
            if isinstance(handle_id_obj, str) and handle_id_obj.strip():
                run_handle_emission: LiveParserEmission = {
                    "kind": "run_handle",
                    "handle_id": handle_id_obj.strip(),
                }
                raw_ref_obj = run_handle_obj.get("raw_ref")
                if isinstance(raw_ref_obj, dict):
                    run_handle_emission["raw_ref"] = cast(RuntimeStreamRawRef, raw_ref_obj)
                if isinstance(session_id, str) and session_id:
                    run_handle_emission["session_id"] = session_id
                emissions.append(run_handle_emission)
        process_events_obj = parsed.get("process_events")
        if isinstance(process_events_obj, list):
            for process_event in process_events_obj:
                if not isinstance(process_event, dict):
                    continue
                process_type_obj = process_event.get("process_type")
                process_type: Literal["reasoning", "tool_call", "command_execution"] | None = (
                    cast(Literal["reasoning", "tool_call", "command_execution"], process_type_obj)
                    if isinstance(process_type_obj, str)
                    and process_type_obj in {"reasoning", "tool_call", "command_execution"}
                    else None
                )
                if process_type not in {"reasoning", "tool_call", "command_execution"}:
                    continue
                summary_obj = process_event.get("summary")
                summary = summary_obj if isinstance(summary_obj, str) and summary_obj.strip() else process_type
                message_id_obj = process_event.get("message_id")
                message_id = (
                    message_id_obj
                    if isinstance(message_id_obj, str) and message_id_obj.strip()
                    else f"{process_type}_buffered"
                )
                process_emission: LiveParserEmission = {
                    "kind": "process_event",
                    "process_type": process_type,
                    "message_id": message_id,
                    "summary": summary,
                }
                classification_obj = process_event.get("classification")
                if isinstance(classification_obj, str) and classification_obj.strip():
                    process_emission["classification"] = classification_obj
                details_obj = process_event.get("details")
                if isinstance(details_obj, dict):
                    process_emission["details"] = details_obj
                text_obj = process_event.get("text")
                if isinstance(text_obj, str) and text_obj.strip():
                    process_emission["text"] = text_obj
                raw_ref_obj = process_event.get("raw_ref")
                if isinstance(raw_ref_obj, dict):
                    process_emission["raw_ref"] = cast(RuntimeStreamRawRef, raw_ref_obj)
                if isinstance(session_id, str) and session_id:
                    process_emission["session_id"] = session_id
                emissions.append(process_emission)
        for item in parsed.get("assistant_messages", []):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            assistant_emission: LiveParserEmission = {"kind": "assistant_message", "text": text}
            message_id_obj = item.get("message_id")
            if isinstance(message_id_obj, str) and message_id_obj.strip():
                assistant_emission["message_id"] = message_id_obj
            raw_ref = item.get("raw_ref")
            if isinstance(raw_ref, dict):
                assistant_emission["raw_ref"] = cast(RuntimeStreamRawRef, raw_ref)
            if isinstance(session_id, str) and session_id:
                assistant_emission["session_id"] = session_id
            emissions.append(assistant_emission)
        for code in parsed.get("diagnostics", []):
            if not isinstance(code, str) or not code:
                continue
            diagnostic_emission: LiveParserEmission = {"kind": "diagnostic", "code": code}
            if isinstance(session_id, str) and session_id:
                diagnostic_emission["session_id"] = session_id
            emissions.append(diagnostic_emission)
        turn_markers_obj = parsed.get("turn_markers")
        if isinstance(turn_markers_obj, list):
            for marker_item in turn_markers_obj:
                if not isinstance(marker_item, dict):
                    continue
                marker_obj = marker_item.get("marker")
                marker = marker_obj if isinstance(marker_obj, str) else None
                if marker not in {"start", "complete"}:
                    continue
                marker_literal: Literal["start", "complete"] = cast(
                    Literal["start", "complete"],
                    marker,
                )
                marker_emission: LiveParserEmission = {"kind": "turn_marker", "marker": marker_literal}
                if marker_literal == "complete":
                    marker_data_obj = marker_item.get("data")
                    if isinstance(marker_data_obj, dict):
                        marker_emission["turn_complete_data"] = marker_data_obj
                    elif isinstance(parsed_turn_complete_data, dict):
                        marker_emission["turn_complete_data"] = parsed_turn_complete_data
                raw_ref_obj = marker_item.get("raw_ref")
                if isinstance(raw_ref_obj, dict):
                    marker_emission["raw_ref"] = cast(RuntimeStreamRawRef, raw_ref_obj)
                if isinstance(session_id, str) and session_id:
                    marker_emission["session_id"] = session_id
                emissions.append(marker_emission)
        if bool(parsed.get("turn_started")):
            emissions.append({"kind": "turn_marker", "marker": "start"})
        if bool(parsed.get("turn_completed")):
            completion_emission: LiveParserEmission = {"kind": "turn_completed"}
            if isinstance(parsed_turn_complete_data, dict):
                completion_emission["turn_complete_data"] = parsed_turn_complete_data
            emissions.append(completion_emission)
        return emissions


class LiveRuntimeEmitterImpl(LiveRuntimeEmitter):
    def __init__(
        self,
        *,
        run_id: str,
        run_dir: Path,
        engine: str,
        attempt_number: int,
        stream_parser: Any,
        fcmp_publisher: FcmpEventPublisher | None = None,
        rasp_publisher: RaspEventPublisher | None = None,
        run_handle_consumer: Callable[[str], Awaitable[dict[str, Any] | None] | dict[str, Any] | None] | None = None,
    ) -> None:
        self._run_id = run_id
        self._run_dir = run_dir
        self._engine = engine
        self._attempt_number = attempt_number
        self._stream_parser = stream_parser
        self._semantic_emissions_terminal_only = bool(
            getattr(stream_parser, "live_semantic_on_finish_only", False)
        )
        self._fcmp_publisher = fcmp_publisher or fcmp_event_publisher
        self._rasp_publisher = rasp_publisher or rasp_event_publisher
        self._run_handle_consumer = run_handle_consumer
        start_live_session = getattr(stream_parser, "start_live_session", None)
        if callable(start_live_session):
            self._parser_session = start_live_session()
        else:
            self._parser_session = _BufferedLiveParserSession(stream_parser=stream_parser)
        self._line_buffers: dict[str, str] = {"stdout": "", "stderr": "", "pty": ""}
        self._line_buffer_start: dict[str, int | None] = {"stdout": None, "stderr": None, "pty": None}
        self._pending_raw_rows: dict[str, list[RuntimeStreamRawRow]] = {"stdout": [], "stderr": [], "pty": []}
        self._suppressed_raw_ranges: dict[str, list[tuple[int, int]]] = {
            "stdout": [],
            "stderr": [],
            "pty": [],
        }
        self._session_id: str | None = None
        self._message_count = 0
        self._promotion = FinalPromotionCoordinator()
        self._turn_start_emitted = False
        self._turn_complete_emitted = False

    async def on_process_started(self, *, event_ts: datetime | None = None) -> None:
        if self._engine not in {"gemini", "iflow"}:
            return
        self._emit_turn_marker(marker="start", raw_ref=None, data=None, event_ts=event_ts)

    async def on_stream_chunk(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
        event_ts: datetime | None = None,
    ) -> None:
        emissions = self._parser_session.feed(
            stream=stream,
            text=text,
            byte_from=byte_from,
            byte_to=byte_to,
        )
        await self._publish_emissions(emissions, event_ts=event_ts)
        self._publish_raw_lines(
            stream=stream,
            text=text,
            byte_from=byte_from,
            byte_to=byte_to,
            event_ts=event_ts,
        )

    async def on_process_exit(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
        event_ts: datetime | None = None,
    ) -> None:
        emissions = self._parser_session.finish(exit_code=exit_code, failure_reason=failure_reason)
        await self._publish_emissions(emissions, event_ts=event_ts)
        self._flush_partial_lines(event_ts=event_ts)
        self._flush_pending_raw_rows(event_ts=event_ts)
        if exit_code == 0 and failure_reason not in {"AUTH_REQUIRED", "TIMEOUT"}:
            self._emit_promoted_and_final(status="succeeded", event_ts=event_ts)

    def _publish_raw_lines(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
        event_ts: datetime | None = None,
    ) -> None:
        buffer = self._line_buffers.get(stream, "")
        buffer_start = self._line_buffer_start.get(stream)
        combined_start = buffer_start if buffer and isinstance(buffer_start, int) else byte_from
        combined = f"{buffer}{text}"
        if "\n" not in combined:
            self._line_buffers[stream] = combined
            self._line_buffer_start[stream] = combined_start
            return
        pieces = combined.splitlines(keepends=True)
        emit_lines = pieces[:-1]
        tail = pieces[-1]
        if tail.endswith("\n"):
            emit_lines.append(tail)
            tail = ""
        self._line_buffers[stream] = tail
        self._line_buffer_start[stream] = combined_start + len("".join(emit_lines).encode("utf-8", errors="replace")) if tail else None
        if not emit_lines:
            return
        line_start = combined_start
        buffered_rows = self._pending_raw_rows.setdefault(stream, [])
        for line in emit_lines:
            encoded = line.encode("utf-8", errors="replace")
            line_end = line_start + len(encoded)
            clean_line = line.rstrip("\n")
            if self._is_raw_span_suppressed(stream=stream, byte_from=line_start, byte_to=line_end):
                line_start = line_end
                continue
            buffered_rows.append(
                {
                    "stream": stream,
                    "line": clean_line,
                    "byte_from": line_start,
                    "byte_to": line_end,
                    "ts": event_ts.isoformat() if isinstance(event_ts, datetime) else None,
                }
            )
            line_start = line_end
        if self._semantic_emissions_terminal_only:
            return
        self._drain_pending_raw_rows(stream=stream, flush_all=False, event_ts=event_ts)

    def _flush_partial_lines(self, *, event_ts: datetime | None = None) -> None:
        for stream, text in list(self._line_buffers.items()):
            if not text:
                continue
            start = self._line_buffer_start.get(stream)
            byte_from = start if isinstance(start, int) else 0
            byte_to = byte_from + len(text.encode("utf-8", errors="replace"))
            if self._is_raw_span_suppressed(stream=stream, byte_from=byte_from, byte_to=byte_to):
                self._line_buffers[stream] = ""
                self._line_buffer_start[stream] = None
                continue
            self._pending_raw_rows.setdefault(stream, []).append(
                {
                    "stream": stream,
                    "line": text,
                    "byte_from": byte_from,
                    "byte_to": byte_to,
                    "ts": event_ts.isoformat() if isinstance(event_ts, datetime) else None,
                }
            )
            self._line_buffers[stream] = ""
            self._line_buffer_start[stream] = None

    def _flush_pending_raw_rows(self, *, event_ts: datetime | None = None) -> None:
        for stream in ("stdout", "stderr", "pty"):
            self._drain_pending_raw_rows(stream=stream, flush_all=True, event_ts=event_ts)

    def _drain_pending_raw_rows(
        self,
        *,
        stream: str,
        flush_all: bool,
        event_ts: datetime | None = None,
    ) -> None:
        pending = self._pending_raw_rows.get(stream, [])
        if not pending:
            return
        coalesced_rows, _stats = coalesce_rasp_raw_rows(pending, min_rows=1)
        if not coalesced_rows:
            self._pending_raw_rows[stream] = []
            return
        if flush_all:
            rows_to_publish = coalesced_rows
            remaining_rows: list[RuntimeStreamRawRow] = []
        else:
            rows_to_publish = coalesced_rows[:-1]
            remaining_rows = coalesced_rows[-1:]
        for row in rows_to_publish:
            self._publish_raw_row(row, event_ts=event_ts)
        self._pending_raw_rows[stream] = remaining_rows

    def _publish_raw_row(self, row: RuntimeStreamRawRow, *, event_ts: datetime | None = None) -> None:
        stream = str(row.get("stream") or "stdout")
        byte_from = max(0, int(row.get("byte_from") or 0))
        byte_to = max(byte_from, int(row.get("byte_to") or byte_from))
        if self._is_raw_span_suppressed(stream=stream, byte_from=byte_from, byte_to=byte_to):
            return
        raw_ref = RuntimeEventRef(
            attempt_number=self._attempt_number,
            stream=stream,
            byte_from=byte_from,
            byte_to=byte_to,
            encoding="utf-8",
        )
        rasp = make_rasp_event(
            run_id=self._run_id,
            seq=1,
            source=RuntimeEventSource(engine=self._engine, parser="live_raw", confidence=1.0),
            category=RuntimeEventCategory.RAW,
            type_name="raw.stderr" if stream == "stderr" else "raw.stdout",
            data={"line": str(row.get("line") or "")},
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            correlation={},
            ts=event_ts or datetime.utcnow(),
        )
        self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)

    async def _publish_emissions(
        self,
        emissions: list[LiveParserEmission],
        *,
        event_ts: datetime | None = None,
    ) -> None:
        for emission in emissions:
            if not isinstance(emission, dict):
                continue
            session_id = emission.get("session_id")
            if isinstance(session_id, str) and session_id:
                self._session_id = session_id
            publish_id = uuid.uuid4().hex
            correlation: dict[str, Any] = {"publish_id": publish_id}
            if self._session_id:
                correlation["session_id"] = self._session_id
            raw_ref_obj = emission.get("raw_ref")
            raw_ref = None
            if isinstance(raw_ref_obj, dict):
                raw_ref = RuntimeEventRef(
                    attempt_number=self._attempt_number,
                    stream=str(raw_ref_obj.get("stream") or "stdout"),
                    byte_from=max(0, int(raw_ref_obj.get("byte_from") or 0)),
                    byte_to=max(0, int(raw_ref_obj.get("byte_to") or 0)),
                    encoding="utf-8",
                )
                self._add_suppressed_raw_ref(raw_ref_obj)
            kind = emission.get("kind")
            if kind == "assistant_message":
                text = emission.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                self._message_count += 1
                message_id_obj = emission.get("message_id")
                message_id = (
                    message_id_obj
                    if isinstance(message_id_obj, str) and message_id_obj.strip()
                    else f"m_{self._attempt_number}_{self._message_count}"
                )
                candidate = self._promotion.register_reasoning_candidate(
                    message_id=message_id,
                    text=text,
                    raw_ref=raw_ref_obj if isinstance(raw_ref_obj, dict) else None,
                    details={"source": "live_semantic"},
                )
                rasp = make_rasp_event(
                    run_id=self._run_id,
                    seq=1,
                    source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.95),
                    category=RuntimeEventCategory.AGENT,
                    type_name="agent.reasoning",
                    data=build_process_payload(
                        message_id=candidate.message_id,
                        summary=candidate.summary,
                        classification="reasoning",
                        details=candidate.details,
                        text=candidate.text,
                    ),
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    correlation=correlation,
                    ts=event_ts or datetime.utcnow(),
                )
                fcmp = make_fcmp_event(
                    run_id=self._run_id,
                    seq=1,
                    engine=self._engine,
                    type_name=FcmpEventType.ASSISTANT_REASONING.value,
                    data=build_process_payload(
                        message_id=candidate.message_id,
                        summary=candidate.summary,
                        classification="reasoning",
                        details=candidate.details,
                        text=candidate.text,
                    ),
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    ts=event_ts or datetime.utcnow(),
                )
                self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)
                self._fcmp_publisher.publish(run_dir=self._run_dir, event=fcmp)
            elif kind == "run_handle":
                handle_id_obj = emission.get("handle_id")
                handle_id = (
                    handle_id_obj.strip()
                    if isinstance(handle_id_obj, str) and handle_id_obj.strip()
                    else None
                )
                if not handle_id:
                    continue
                rasp = make_rasp_event(
                    run_id=self._run_id,
                    seq=1,
                    source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.95),
                    category=RuntimeEventCategory.LIFECYCLE,
                    type_name="lifecycle.run_handle",
                    data={"handle_id": handle_id},
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    correlation=correlation,
                    ts=event_ts or datetime.utcnow(),
                )
                self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)
                consumer = self._run_handle_consumer
                if callable(consumer):
                    consume_result = consumer(handle_id)
                    if inspect.isawaitable(consume_result):
                        consume_result = await consume_result
                    if isinstance(consume_result, dict) and str(consume_result.get("status") or "") == "changed":
                        previous_handle_obj = consume_result.get("previous_handle_id")
                        previous_handle = (
                            previous_handle_obj.strip()
                            if isinstance(previous_handle_obj, str) and previous_handle_obj.strip()
                            else "unknown"
                        )
                        detail = (
                            f"Run handle changed for attempt {self._attempt_number}: "
                            f"{previous_handle} -> {handle_id}"
                        )
                        diag_payload = {"code": "RUN_HANDLE_CHANGED", "detail": detail}
                        diag_rasp = make_rasp_event(
                            run_id=self._run_id,
                            seq=1,
                            source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.9),
                            category=RuntimeEventCategory.DIAGNOSTIC,
                            type_name="diagnostic.warning",
                            data=diag_payload,
                            attempt_number=self._attempt_number,
                            raw_ref=raw_ref,
                            correlation={"publish_id": uuid.uuid4().hex, **({"session_id": self._session_id} if self._session_id else {})},
                            ts=event_ts or datetime.utcnow(),
                        )
                        diag_fcmp = make_fcmp_event(
                            run_id=self._run_id,
                            seq=1,
                            engine=self._engine,
                            type_name=FcmpEventType.DIAGNOSTIC_WARNING.value,
                            data=diag_payload,
                            attempt_number=self._attempt_number,
                            raw_ref=raw_ref,
                            ts=event_ts or datetime.utcnow(),
                        )
                        self._rasp_publisher.publish(run_dir=self._run_dir, event=diag_rasp)
                        self._fcmp_publisher.publish(run_dir=self._run_dir, event=diag_fcmp)
            elif kind == "process_event":
                process_type = emission.get("process_type")
                if process_type not in {"reasoning", "tool_call", "command_execution"}:
                    continue
                summary_obj = emission.get("summary")
                summary = summary_obj if isinstance(summary_obj, str) and summary_obj.strip() else process_type
                message_id_obj = emission.get("message_id")
                if isinstance(message_id_obj, str) and message_id_obj.strip():
                    message_id = message_id_obj
                else:
                    message_id = f"{process_type}_{self._attempt_number}_{self._message_count + 1}"
                classification_obj = emission.get("classification")
                classification = (
                    classification_obj
                    if isinstance(classification_obj, str) and classification_obj.strip()
                    else process_type
                )
                details_obj = emission.get("details")
                details = details_obj if isinstance(details_obj, dict) else {}
                text_obj = emission.get("text")
                text_value = text_obj if isinstance(text_obj, str) and text_obj.strip() else None
                type_pairs = {
                    "reasoning": ("agent.reasoning", FcmpEventType.ASSISTANT_REASONING.value),
                    "tool_call": ("agent.tool_call", FcmpEventType.ASSISTANT_TOOL_CALL.value),
                    "command_execution": (
                        "agent.command_execution",
                        FcmpEventType.ASSISTANT_COMMAND_EXECUTION.value,
                    ),
                }
                rasp_type, fcmp_type = type_pairs[process_type]
                payload = build_process_payload(
                    message_id=message_id,
                    summary=summary,
                    classification=classification,
                    details=details,
                    text=text_value,
                )
                rasp = make_rasp_event(
                    run_id=self._run_id,
                    seq=1,
                    source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.9),
                    category=RuntimeEventCategory.AGENT,
                    type_name=rasp_type,
                    data=payload,
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    correlation=correlation,
                    ts=event_ts or datetime.utcnow(),
                )
                fcmp = make_fcmp_event(
                    run_id=self._run_id,
                    seq=1,
                    engine=self._engine,
                    type_name=fcmp_type,
                    data=payload,
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    ts=event_ts or datetime.utcnow(),
                )
                self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)
                self._fcmp_publisher.publish(run_dir=self._run_dir, event=fcmp)
            elif kind == "turn_marker":
                marker_obj = emission.get("marker")
                marker = marker_obj if isinstance(marker_obj, str) else None
                if marker == "start":
                    marker_literal: Literal["start", "complete"] = "start"
                elif marker == "complete":
                    marker_literal = "complete"
                else:
                    continue
                turn_complete_data = (
                    emission.get("turn_complete_data")
                    if isinstance(emission.get("turn_complete_data"), dict)
                    else None
                )
                self._emit_turn_marker(
                    marker=marker_literal,
                    raw_ref=raw_ref,
                    data=turn_complete_data,
                    event_ts=event_ts,
                )
            elif kind == "turn_completed":
                turn_complete_data = (
                    emission.get("turn_complete_data")
                    if isinstance(emission.get("turn_complete_data"), dict)
                    else None
                )
                self._emit_turn_marker(
                    marker="complete",
                    raw_ref=raw_ref,
                    data=turn_complete_data,
                    event_ts=event_ts,
                )
                self._emit_promoted_and_final(status="turn_completed", event_ts=event_ts)
            elif kind == "diagnostic":
                code = emission.get("code")
                if not isinstance(code, str) or not code:
                    continue
                rasp = make_rasp_event(
                    run_id=self._run_id,
                    seq=1,
                    source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.6),
                    category=RuntimeEventCategory.DIAGNOSTIC,
                    type_name="diagnostic.warning",
                    data={"code": code},
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    correlation=correlation,
                    ts=event_ts or datetime.utcnow(),
                )
                fcmp = make_fcmp_event(
                    run_id=self._run_id,
                    seq=1,
                    engine=self._engine,
                    type_name=FcmpEventType.DIAGNOSTIC_WARNING.value,
                    data={"code": code},
                    attempt_number=self._attempt_number,
                    raw_ref=raw_ref,
                    ts=event_ts or datetime.utcnow(),
                )
                self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)
                self._fcmp_publisher.publish(run_dir=self._run_dir, event=fcmp)

    def _emit_turn_marker(
        self,
        *,
        marker: Literal["start", "complete"],
        raw_ref: RuntimeEventRef | None,
        data: dict[str, Any] | None,
        event_ts: datetime | None = None,
    ) -> None:
        if marker == "start":
            if self._turn_start_emitted:
                return
            self._turn_start_emitted = True
            type_name = "agent.turn_start"
            payload: dict[str, Any] = {}
        else:
            if self._turn_complete_emitted:
                return
            self._turn_complete_emitted = True
            type_name = "agent.turn_complete"
            payload = data if isinstance(data, dict) else {}

        correlation: dict[str, Any] = {"publish_id": uuid.uuid4().hex}
        if self._session_id:
            correlation["session_id"] = self._session_id
        rasp = make_rasp_event(
            run_id=self._run_id,
            seq=1,
            source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.9),
            category=RuntimeEventCategory.AGENT,
            type_name=type_name,
            data=payload,
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            correlation=correlation,
            ts=event_ts or datetime.utcnow(),
        )
        self._rasp_publisher.publish(run_dir=self._run_dir, event=rasp)

    def _add_suppressed_raw_ref(self, raw_ref_obj: RuntimeStreamRawRef) -> None:
        stream = str(raw_ref_obj.get("stream") or "stdout")
        if stream not in self._suppressed_raw_ranges:
            return
        byte_from = max(0, int(raw_ref_obj.get("byte_from") or 0))
        byte_to = max(byte_from, int(raw_ref_obj.get("byte_to") or byte_from))
        if byte_to <= byte_from:
            return
        self._suppressed_raw_ranges[stream].append((byte_from, byte_to))

    def _is_raw_span_suppressed(self, *, stream: str, byte_from: int, byte_to: int) -> bool:
        ranges = self._suppressed_raw_ranges.get(stream)
        if not ranges:
            return False
        for start, end in ranges:
            if byte_from < end and byte_to > start:
                return True
        return False

    def _emit_promoted_and_final(self, *, status: str, event_ts: datetime | None = None) -> None:
        candidate = (
            self._promotion.promote_on_turn_end()
            if status == "turn_completed"
            else self._promotion.fallback_promote_for_status(status)
        )
        if candidate is None:
            return
        raw_ref = None
        if isinstance(candidate.raw_ref, dict):
            raw_ref = RuntimeEventRef(
                attempt_number=self._attempt_number,
                stream=str(candidate.raw_ref.get("stream") or "stdout"),
                byte_from=max(0, int(candidate.raw_ref.get("byte_from") or 0)),
                byte_to=max(0, int(candidate.raw_ref.get("byte_to") or 0)),
                encoding="utf-8",
            )
        promoted_payload = FinalPromotionCoordinator.promoted_payload(candidate)
        final_payload = FinalPromotionCoordinator.final_payload(candidate)
        correlation: dict[str, Any] = {"publish_id": uuid.uuid4().hex}
        if self._session_id:
            correlation["session_id"] = self._session_id
        promoted_rasp = make_rasp_event(
            run_id=self._run_id,
            seq=1,
            source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.95),
            category=RuntimeEventCategory.AGENT,
            type_name="agent.message.promoted",
            data=promoted_payload,
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            correlation=correlation,
            ts=event_ts or datetime.utcnow(),
        )
        promoted_fcmp = make_fcmp_event(
            run_id=self._run_id,
            seq=1,
            engine=self._engine,
            type_name=FcmpEventType.ASSISTANT_MESSAGE_PROMOTED.value,
            data=promoted_payload,
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            ts=event_ts or datetime.utcnow(),
        )
        final_rasp = make_rasp_event(
            run_id=self._run_id,
            seq=1,
            source=RuntimeEventSource(engine=self._engine, parser="live_semantic", confidence=0.95),
            category=RuntimeEventCategory.AGENT,
            type_name="agent.message.final",
            data=final_payload,
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            correlation={"publish_id": uuid.uuid4().hex, **({"session_id": self._session_id} if self._session_id else {})},
            ts=event_ts or datetime.utcnow(),
        )
        final_fcmp = make_fcmp_event(
            run_id=self._run_id,
            seq=1,
            engine=self._engine,
            type_name=FcmpEventType.ASSISTANT_MESSAGE_FINAL.value,
            data=final_payload,
            attempt_number=self._attempt_number,
            raw_ref=raw_ref,
            ts=event_ts or datetime.utcnow(),
        )
        self._rasp_publisher.publish(run_dir=self._run_dir, event=promoted_rasp)
        self._fcmp_publisher.publish(run_dir=self._run_dir, event=promoted_fcmp)
        self._rasp_publisher.publish(run_dir=self._run_dir, event=final_rasp)
        self._fcmp_publisher.publish(run_dir=self._run_dir, event=final_fcmp)


fcmp_event_publisher = FcmpEventPublisher()
rasp_event_publisher = RaspEventPublisher()


async def flush_live_audit_mirrors(*, run_id: Optional[str] = None) -> None:
    await asyncio.gather(
        fcmp_event_publisher.drain_mirror(run_id=run_id),
        rasp_event_publisher.drain_mirror(run_id=run_id),
    )
