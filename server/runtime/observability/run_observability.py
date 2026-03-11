import asyncio
import base64
import binascii
import json
import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from server.config import config
from server.runtime.chat_replay.factories import derive_chat_replay_rows_from_fcmp
from server.runtime.chat_replay.live_journal import chat_replay_live_journal
from server.runtime.protocol.event_protocol import (
    RebuildMode,
    build_fcmp_events,
    build_rasp_events,
    compute_protocol_metrics,
    read_jsonl,
    translate_orchestrator_event_to_fcmp_specs,
    write_jsonl,
)
from server.runtime.protocol.factories import make_fcmp_event
from server.runtime.protocol.contracts import RuntimeParserResolverPort
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_chat_replay_event,
    validate_fcmp_event,
    validate_orchestrator_event,
    validate_rasp_event,
)
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.observability.rasp_live_journal import rasp_live_journal
from server.runtime.protocol.live_publish import (
    FcmpEventPublisher,
    LiveRuntimeEmitterImpl,
    RaspEventPublisher,
    flush_live_audit_mirrors,
)
from server.runtime.observability.contracts import (
    QueuedResumeRedriver,
    RunStorePort,
    WaitingAuthReconciler,
    WorkspacePort,
)
from server.services.platform.async_compat import maybe_await
from server.services.skill.skill_browser import (
    build_preview_payload,
)
from server.services.platform.run_file_filter_service import (
    normalize_relative_path,
    run_file_filter_service,
)


RUNNING_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
AUDIT_DIR_NAME = ".audit"
RASP_EVENTS_FILE_PREFIX = "events"
PARSER_DIAGNOSTICS_FILE_PREFIX = "parser_diagnostics"
FCMP_EVENTS_FILE_PREFIX = "fcmp_events"
PROTOCOL_METRICS_FILE_PREFIX = "protocol_metrics"
ORCHESTRATOR_EVENTS_FILE_PREFIX = "orchestrator_events"
IO_CHUNKS_FILE_PREFIX = "io_chunks"
ATTEMPT_FILE_PATTERNS = (
    re.compile(r"^meta\.(\d+)\.json$"),
    re.compile(r"^events\.(\d+)\.jsonl$"),
    re.compile(r"^fcmp_events\.(\d+)\.jsonl$"),
    re.compile(r"^orchestrator_events\.(\d+)\.jsonl$"),
    re.compile(r"^io_chunks\.(\d+)\.jsonl$"),
    re.compile(r"^stdout\.(\d+)\.log$"),
    re.compile(r"^stderr\.(\d+)\.log$"),
    re.compile(r"^pty-output\.(\d+)\.log$"),
)
TIMELINE_STREAM_PRIORITY: Dict[str, int] = {
    "orchestrator": 0,
    "rasp": 1,
    "fcmp": 2,
    "chat": 3,
    "client": 4,
}
TIMELINE_LANE_BY_STREAM: Dict[str, str] = {
    "orchestrator": "orchestrator",
    "rasp": "parser_rasp",
    "fcmp": "protocol_fcmp",
    "chat": "chat_history",
    "client": "client",
}
TIMELINE_PROTOCOL_WINDOW_LIMIT = 300
TIMELINE_CACHE_MAX_ENTRIES = 32

class _UnconfiguredRunStore:
    def get_request(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def get_request_with_run(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def list_requests_with_runs(self, limit: int = 200):
        _ = limit
        raise RuntimeError("Run observability run_store port is not configured")

    def get_pending_interaction(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def get_pending_auth(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def get_pending_auth_method_selection(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def get_interaction_count(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def list_interaction_history(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")

    def get_effective_session_timeout(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run observability run_store port is not configured")


class _UnconfiguredWorkspace:
    def get_run_dir(self, run_id: str):
        _ = run_id
        raise RuntimeError("Run observability workspace port is not configured")


run_store: RunStorePort | Any = _UnconfiguredRunStore()
workspace_manager: WorkspacePort | Any = _UnconfiguredWorkspace()
parser_resolver: RuntimeParserResolverPort | None = None
waiting_auth_reconciler: WaitingAuthReconciler | None = None
queued_resume_redriver: QueuedResumeRedriver | None = None


def configure_run_observability_ports(
    *,
    run_store_backend: RunStorePort | Any,
    workspace_backend: WorkspacePort | Any,
    parser_resolver_backend: RuntimeParserResolverPort | None = None,
    waiting_auth_reconciler_backend: WaitingAuthReconciler | None = None,
    queued_resume_redriver_backend: QueuedResumeRedriver | None = None,
) -> None:
    global run_store, workspace_manager, parser_resolver, waiting_auth_reconciler, queued_resume_redriver
    run_store = run_store_backend
    workspace_manager = workspace_backend
    parser_resolver = parser_resolver_backend
    waiting_auth_reconciler = waiting_auth_reconciler_backend
    queued_resume_redriver = queued_resume_redriver_backend


def _resolve_conversation_mode(client_metadata: dict[str, Any] | None) -> str:
    if not isinstance(client_metadata, dict):
        return "session"
    raw = client_metadata.get("conversation_mode")
    if not isinstance(raw, str):
        return "session"
    normalized = raw.strip().lower()
    if normalized in {"session", "non_session"}:
        return normalized
    return "session"


class RunObservabilityService:
    def __init__(self) -> None:
        self._timeline_cache: Dict[str, Dict[str, Any]] = {}
        self._timeline_cache_order: list[str] = []

    def _run_store(self):
        return run_store

    def _workspace(self):
        return workspace_manager

    async def _reconcile_waiting_auth_if_needed(self, request_id: str, run_status: str) -> None:
        if run_status != "waiting_auth" or not request_id or waiting_auth_reconciler is None:
            return
        await waiting_auth_reconciler(request_id=request_id)

    async def _redrive_queued_resume_if_needed(self, request_id: str, run_status: str) -> None:
        if run_status != "queued" or not request_id or queued_resume_redriver is None:
            return
        request_record = await maybe_await(self._run_store().get_request(request_id))
        if not isinstance(request_record, dict):
            return
        run_id_obj = request_record.get("run_id")
        engine_name_obj = request_record.get("engine")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            return
        if not isinstance(engine_name_obj, str) or not engine_name_obj:
            return
        await queued_resume_redriver(
            request_id=request_id,
            run_id=run_id_obj,
            engine_name=engine_name_obj,
            run_store_backend=self._run_store(),
        )

    def format_sse_frame(self, event: str, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {encoded}\n\n"

    def read_log_increment(
        self,
        path: Path,
        from_offset: int,
        max_bytes: int = 8 * 1024,
    ) -> Dict[str, Any]:
        if max_bytes <= 0:
            max_bytes = 8 * 1024
        safe_from = max(0, int(from_offset))
        if not path.exists() or not path.is_file():
            return {"from": safe_from, "to": safe_from, "chunk": ""}

        file_size = path.stat().st_size
        start = min(safe_from, file_size)
        if start >= file_size:
            return {"from": start, "to": start, "chunk": ""}

        read_size = min(file_size - start, max_bytes)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(read_size)
        end = start + len(data)
        return {
            "from": start,
            "to": end,
            "chunk": data.decode("utf-8", errors="replace"),
        }

    async def read_log_range(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        stream: str,
        byte_from: int,
        byte_to: int,
        attempt: Optional[int] = None,
    ) -> Dict[str, Any]:
        safe_stream = stream.strip().lower()
        if safe_stream not in {"stdout", "stderr", "pty"}:
            raise ValueError("stream must be one of: stdout, stderr, pty")
        status_payload = self._read_status_payload(run_dir)
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        attempt_number = await self._resolve_attempt_number(
            request_id,
            status=status,
            run_dir=run_dir,
            requested_attempt=attempt,
        )
        audit_dir = run_dir / AUDIT_DIR_NAME
        if safe_stream == "pty":
            attempted = audit_dir / f"pty-output.{attempt_number}.log"
        else:
            attempted = audit_dir / f"{safe_stream}.{attempt_number}.log"
        path = attempted
        start = max(0, int(byte_from))
        end = max(start, int(byte_to))
        if not path.exists() or not path.is_file():
            return {"stream": safe_stream, "byte_from": start, "byte_to": start, "chunk": ""}
        raw = path.read_bytes()
        size = len(raw)
        start = min(start, size)
        end = min(end, size)
        if end <= start:
            return {"stream": safe_stream, "byte_from": start, "byte_to": start, "chunk": ""}
        chunk = raw[start:end].decode("utf-8", errors="replace")
        return {"stream": safe_stream, "byte_from": start, "byte_to": end, "chunk": chunk}

    async def iter_sse_events(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        cursor: int = 0,
        heartbeat_interval_sec: float = 5.0,
        poll_interval_sec: float = 0.2,
        is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        status_payload = self._read_status_payload(run_dir)
        status = status_payload.get("status")
        if not isinstance(status, str) or not status:
            status = "queued"
        history_payload = await self.get_event_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=max(0, int(cursor)) + 1,
            to_seq=None,
            from_ts=None,
            to_ts=None,
        )
        snapshot = {
            "status": status,
            "cursor": max(0, int(cursor)),
            "cursor_floor": history_payload.get("cursor_floor", 0),
            "cursor_ceiling": history_payload.get("cursor_ceiling", 0),
            "replay_source": history_payload.get("source", "audit"),
        }
        pending_id = await self._read_pending_interaction_id(request_id)
        if pending_id is not None:
            snapshot["pending_interaction_id"] = pending_id
        pending_auth_session_id = await self._read_pending_auth_session_id(request_id)
        if pending_auth_session_id is not None:
            snapshot["pending_auth_session_id"] = pending_auth_session_id
        yield {"event": "snapshot", "data": snapshot}

        last_heartbeat_at = time.monotonic()
        last_chat_event_seq = max(0, int(cursor))
        bootstrap_events = history_payload.get("events", [])
        for event in bootstrap_events:
            seq_obj = event.get("seq")
            if not isinstance(seq_obj, int) or seq_obj <= last_chat_event_seq:
                continue
            yield {"event": "chat_event", "data": event}
            last_chat_event_seq = seq_obj

        queue, unsubscribe = fcmp_live_journal.subscribe(run_id=run_dir.name)
        terminal_idle_cycles = 0
        try:
            while True:
                if is_disconnected is not None and await is_disconnected():
                    return

                emitted = False
                try:
                    queued_event = await asyncio.wait_for(queue.get(), timeout=poll_interval_sec)
                except asyncio.TimeoutError:
                    queued_event = None

                if isinstance(queued_event, dict):
                    seq_obj = queued_event.get("seq")
                    if isinstance(seq_obj, int) and seq_obj > last_chat_event_seq:
                        yield {"event": "chat_event", "data": queued_event}
                        last_chat_event_seq = seq_obj
                        emitted = True

                catchup_payload = await self.get_event_history_payload(
                    run_dir=run_dir,
                    request_id=request_id,
                    from_seq=last_chat_event_seq + 1,
                    to_seq=None,
                    from_ts=None,
                    to_ts=None,
                )
                for event in catchup_payload.get("events", []):
                    seq_obj = event.get("seq")
                    if not isinstance(seq_obj, int) or seq_obj <= last_chat_event_seq:
                        continue
                    yield {"event": "chat_event", "data": event}
                    emitted = True
                    last_chat_event_seq = seq_obj

                status_payload = self._read_status_payload(run_dir)
                status_obj = status_payload.get("status")
                current_status = status_obj if isinstance(status_obj, str) and status_obj else status

                if current_status in {"waiting_user", "waiting_auth", *TERMINAL_STATUSES}:
                    if emitted:
                        terminal_idle_cycles = 0
                    else:
                        terminal_idle_cycles += 1
                    if terminal_idle_cycles >= 2:
                        return
                else:
                    terminal_idle_cycles = 0

                now = time.monotonic()
                if not emitted and now - last_heartbeat_at >= heartbeat_interval_sec:
                    yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}
                    last_heartbeat_at = now
                elif emitted:
                    last_heartbeat_at = now
        finally:
            unsubscribe()

    async def iter_chat_events(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        cursor: int = 0,
        heartbeat_interval_sec: float = 5.0,
        poll_interval_sec: float = 0.2,
        is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        status_payload = self._read_status_payload(run_dir)
        status = status_payload.get("status")
        if not isinstance(status, str) or not status:
            status = "queued"
        history_payload = await self.get_chat_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=max(0, int(cursor)) + 1,
            to_seq=None,
            from_ts=None,
            to_ts=None,
        )
        snapshot = {
            "status": status,
            "cursor": max(0, int(cursor)),
            "cursor_floor": history_payload.get("cursor_floor", 0),
            "cursor_ceiling": history_payload.get("cursor_ceiling", 0),
            "replay_source": history_payload.get("source", "audit"),
        }
        pending_id = await self._read_pending_interaction_id(request_id)
        if pending_id is not None:
            snapshot["pending_interaction_id"] = pending_id
        pending_auth_session_id = await self._read_pending_auth_session_id(request_id)
        if pending_auth_session_id is not None:
            snapshot["pending_auth_session_id"] = pending_auth_session_id
        yield {"event": "snapshot", "data": snapshot}

        last_chat_seq = max(0, int(cursor))
        bootstrap_events = history_payload.get("events", [])
        for event in bootstrap_events:
            seq_obj = event.get("seq")
            if not isinstance(seq_obj, int) or seq_obj <= last_chat_seq:
                continue
            yield {"event": "chat_event", "data": event}
            last_chat_seq = seq_obj

        queue, unsubscribe = chat_replay_live_journal.subscribe(run_id=run_dir.name)
        terminal_idle_cycles = 0
        last_heartbeat_at = time.monotonic()
        try:
            while True:
                if is_disconnected is not None and await is_disconnected():
                    return

                emitted = False
                try:
                    queued_event = await asyncio.wait_for(queue.get(), timeout=poll_interval_sec)
                except asyncio.TimeoutError:
                    queued_event = None

                if isinstance(queued_event, dict):
                    seq_obj = queued_event.get("seq")
                    if isinstance(seq_obj, int) and seq_obj > last_chat_seq:
                        yield {"event": "chat_event", "data": queued_event}
                        last_chat_seq = seq_obj
                        emitted = True

                catchup_payload = await self.get_chat_history_payload(
                    run_dir=run_dir,
                    request_id=request_id,
                    from_seq=last_chat_seq + 1,
                    to_seq=None,
                    from_ts=None,
                    to_ts=None,
                )
                for event in catchup_payload.get("events", []):
                    seq_obj = event.get("seq")
                    if not isinstance(seq_obj, int) or seq_obj <= last_chat_seq:
                        continue
                    yield {"event": "chat_event", "data": event}
                    emitted = True
                    last_chat_seq = seq_obj

                status_payload = self._read_status_payload(run_dir)
                status_obj = status_payload.get("status")
                current_status = status_obj if isinstance(status_obj, str) and status_obj else status

                if current_status in {"waiting_user", "waiting_auth", *TERMINAL_STATUSES}:
                    if emitted:
                        terminal_idle_cycles = 0
                    else:
                        terminal_idle_cycles += 1
                    if terminal_idle_cycles >= 2:
                        return
                else:
                    terminal_idle_cycles = 0

                now = time.monotonic()
                if not emitted and now - last_heartbeat_at >= heartbeat_interval_sec:
                    yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}
                    last_heartbeat_at = now
                elif emitted:
                    last_heartbeat_at = now
        finally:
            unsubscribe()

    async def _drain_trailing_chat_events(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        last_chat_event_seq: int,
        poll_interval_sec: float,
        expected_attempt: int | None = None,
        drain_window_sec: float = 5.0,
    ) -> tuple[List[Dict[str, Any]], int]:
        drained: List[Dict[str, Any]] = []
        deadline = time.monotonic() + max(0.1, float(drain_window_sec))
        idle_cycles = 0
        latest_attempt_seen = self._latest_attempt_number(run_dir)
        while time.monotonic() < deadline:
            protocol_payload = await self.list_event_history(
                run_dir=run_dir,
                request_id=request_id,
                from_seq=last_chat_event_seq + 1,
                to_seq=None,
                from_ts=None,
                to_ts=None,
            )
            emitted = False
            for event in protocol_payload:
                seq_obj = event.get("seq")
                if not isinstance(seq_obj, int) or seq_obj <= last_chat_event_seq:
                    continue
                drained.append(event)
                last_chat_event_seq = seq_obj
                emitted = True

            current_latest_attempt = self._latest_attempt_number(run_dir)
            attempt_advanced = current_latest_attempt > latest_attempt_seen
            latest_attempt_seen = current_latest_attempt
            waiting_for_expected_attempt = (
                isinstance(expected_attempt, int)
                and expected_attempt > 0
                and latest_attempt_seen < expected_attempt
            )
            if emitted:
                idle_cycles = 0
            else:
                idle_cycles += 1
            if drained and idle_cycles >= 1 and not attempt_advanced and not waiting_for_expected_attempt:
                break
            if idle_cycles >= 3 and not attempt_advanced and not waiting_for_expected_attempt:
                break
            await asyncio.sleep(min(max(poll_interval_sec, 0.01), 0.1))
        return drained, last_chat_event_seq

    def _read_expected_attempt_number(self, status_payload: Dict[str, Any]) -> int | None:
        current_attempt_obj = status_payload.get("current_attempt")
        if isinstance(current_attempt_obj, int) and current_attempt_obj > 0:
            return current_attempt_obj
        if isinstance(current_attempt_obj, str):
            try:
                current_attempt = int(current_attempt_obj)
            except ValueError:
                return None
            if current_attempt > 0:
                return current_attempt
        return None

    async def list_event_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload = await self.get_event_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        events_obj = payload.get("events")
        return events_obj if isinstance(events_obj, list) else []

    async def list_chat_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload = await self.get_chat_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        events_obj = payload.get("events")
        return events_obj if isinstance(events_obj, list) else []

    async def get_chat_history_payload(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_id = run_dir.name
        requested_from = int(from_seq) if from_seq is not None else None
        live_payload = chat_replay_live_journal.replay(
            run_id=run_id,
            after_seq=max(0, (requested_from or 1) - 1),
        )
        live_rows = self._filter_events(
            rows=live_payload.get("events", []),
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        live_floor = int(live_payload.get("cursor_floor") or 0)
        live_ceiling = int(live_payload.get("cursor_ceiling") or 0)
        needs_audit = not live_payload.get("has_live")
        if requested_from is None:
            needs_audit = True
        elif live_floor > 0 and requested_from < live_floor:
            needs_audit = True
        audit_rows: List[Dict[str, Any]] = []
        if needs_audit:
            audit_rows = await self._list_chat_history_from_audit(
                run_dir=run_dir,
                request_id=request_id,
                from_seq=from_seq,
                to_seq=to_seq,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        merged = self._merge_chat_rows(audit_rows, live_rows)
        source = "live" if live_rows and not audit_rows else "audit"
        if live_rows and audit_rows:
            source = "mixed"
        if not live_rows and not audit_rows:
            source = "audit"
        return {
            "events": merged,
            "source": source,
            "cursor_floor": live_floor,
            "cursor_ceiling": live_ceiling,
        }

    async def get_event_history_payload(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_id = run_dir.name
        requested_from = int(from_seq) if from_seq is not None else None
        live_payload = fcmp_live_journal.replay(
            run_id=run_id,
            after_seq=max(0, (requested_from or 1) - 1),
        )
        live_rows = self._filter_events(
            rows=live_payload.get("events", []),
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        live_floor = int(live_payload.get("cursor_floor") or 0)
        live_ceiling = int(live_payload.get("cursor_ceiling") or 0)
        needs_audit = not live_payload.get("has_live")
        if requested_from is None:
            needs_audit = True
        elif live_floor > 0 and requested_from < live_floor:
            needs_audit = True
        audit_rows: List[Dict[str, Any]] = []
        if needs_audit:
            audit_rows = await self._list_event_history_from_audit(
                run_dir=run_dir,
                request_id=request_id,
                from_seq=from_seq,
                to_seq=to_seq,
                from_ts=from_ts,
                to_ts=to_ts,
            )
        merged = self._merge_fcmp_rows(audit_rows, live_rows)
        source = "live" if live_rows and not audit_rows else "audit"
        if live_rows and audit_rows:
            source = "mixed"
        if not live_rows and not audit_rows:
            source = "audit"
        return {
            "events": merged,
            "source": source,
            "cursor_floor": live_floor,
            "cursor_ceiling": live_ceiling,
        }

    async def _list_chat_history_from_audit(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int],
        to_seq: Optional[int],
        from_ts: Optional[str],
        to_ts: Optional[str],
    ) -> List[Dict[str, Any]]:
        audit_path = run_dir / AUDIT_DIR_NAME / "chat_replay.jsonl"
        rows: List[Dict[str, Any]]
        if audit_path.exists() and audit_path.is_file():
            rows = self._filter_valid_chat_rows(
                rows=read_jsonl(audit_path),
                context=f"chat-audit:{request_id or run_dir.name}",
            )
        else:
            rows = await self._derive_chat_history_from_fcmp_audit(
                run_dir=run_dir,
                request_id=request_id,
            )
        rows.sort(key=lambda row: (int(row.get("seq") or 0), str(row.get("created_at") or "")))
        return self._filter_events(
            rows=rows,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    async def _list_event_history_from_audit(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int],
        to_seq: Optional[int],
        from_ts: Optional[str],
        to_ts: Optional[str],
    ) -> List[Dict[str, Any]]:
        attempts = self._list_available_attempts(run_dir)
        if not attempts:
            attempts = [1]
        rows: List[Dict[str, Any]] = []
        for attempt_number in attempts:
            payload = await self.list_protocol_history(
                run_dir=run_dir,
                request_id=request_id,
                stream="fcmp",
                from_seq=None,
                to_seq=None,
                from_ts=None,
                to_ts=None,
                attempt=attempt_number,
            )
            if isinstance(payload, dict):
                events_obj = payload.get("events")
                if isinstance(events_obj, list):
                    rows.extend(events_obj)
            elif isinstance(payload, list):
                rows.extend(payload)
        rows.sort(key=lambda row: (int(row.get("seq") or 0), str(row.get("ts") or "")))
        rows = self._ensure_global_fcmp_seq(rows)
        return self._filter_events(
            rows=rows,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    async def _derive_chat_history_from_fcmp_audit(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        fcmp_rows = await self._list_event_history_from_audit(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=None,
            to_seq=None,
            from_ts=None,
            to_ts=None,
        )
        derived: List[Dict[str, Any]] = []
        next_seq = 1
        for row in fcmp_rows:
            for chat_row in derive_chat_replay_rows_from_fcmp(row):
                row_copy = dict(chat_row)
                row_copy["seq"] = next_seq
                next_seq += 1
                try:
                    validate_chat_replay_event(row_copy)
                except ProtocolSchemaViolation as exc:
                    logger.warning(
                        "Skip invalid chat replay row during FCMP fallback (%s): %s",
                        request_id or run_dir.name,
                        str(exc),
                    )
                    continue
                derived.append(row_copy)
        return derived

    def _merge_fcmp_rows(
        self,
        audit_rows: List[Dict[str, Any]],
        live_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[int, Dict[str, Any]] = {}
        for row in audit_rows:
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                merged[seq_obj] = row
        for row in live_rows:
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                merged[seq_obj] = row
        return [merged[key] for key in sorted(merged)]

    def _merge_chat_rows(
        self,
        audit_rows: List[Dict[str, Any]],
        live_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[int, Dict[str, Any]] = {}
        for row in audit_rows:
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                merged[seq_obj] = row
        for row in live_rows:
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                merged[seq_obj] = row
        return [merged[key] for key in sorted(merged)]

    async def list_protocol_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        stream: str,
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        attempt: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized_stream = stream.strip().lower()
        if normalized_stream not in {"fcmp", "rasp", "orchestrator"}:
            raise ValueError("stream must be one of: fcmp, rasp, orchestrator")

        status_payload = self._read_status_payload(run_dir)
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        terminal_status = status in TERMINAL_STATUSES
        selected_attempt = await self._resolve_attempt_number(
            request_id=request_id,
            status=status,
            run_dir=run_dir,
            requested_attempt=attempt,
        )
        live_payload: Dict[str, Any]
        live_rows: List[Dict[str, Any]]
        live_floor = 0
        live_ceiling = 0
        if terminal_status and normalized_stream in {"fcmp", "rasp"}:
            await flush_live_audit_mirrors(run_id=run_dir.name)
            live_payload = {"events": [], "cursor_floor": 0, "cursor_ceiling": 0}
            live_rows = []
        else:
            live_payload = self._get_live_protocol_payload(
                run_dir=run_dir,
                stream=normalized_stream,
                attempt_number=selected_attempt,
                from_seq=from_seq,
                to_seq=to_seq,
                from_ts=from_ts,
                to_ts=to_ts,
            )
            live_rows_obj = live_payload.get("events")
            live_rows = live_rows_obj if isinstance(live_rows_obj, list) else []
            live_floor_obj = live_payload.get("cursor_floor")
            live_ceiling_obj = live_payload.get("cursor_ceiling")
            try:
                live_floor = int(live_floor_obj or 0)
            except (TypeError, ValueError):
                live_floor = 0
            try:
                live_ceiling = int(live_ceiling_obj or 0)
            except (TypeError, ValueError):
                live_ceiling = 0
        requested_from = int(from_seq) if from_seq is not None else None
        paths = self._protocol_paths(run_dir, selected_attempt)
        needs_audit = normalized_stream == "orchestrator"
        if normalized_stream in {"fcmp", "rasp"}:
            if terminal_status:
                needs_audit = True
            elif requested_from is None:
                needs_audit = True
            elif live_floor > 0 and requested_from < live_floor:
                needs_audit = True
            elif not live_rows:
                needs_audit = True
        context = f"history:{normalized_stream}:{request_id or run_dir.name}"
        if normalized_stream == "fcmp":
            self.reindex_fcmp_global_seq(run_dir)
            rows = self._filter_valid_fcmp_rows(
                rows=read_jsonl(paths["fcmp"]),
                context=context,
            )
        elif normalized_stream == "rasp":
            rows = self._filter_valid_rasp_rows(
                rows=read_jsonl(paths["events"]),
                context=context,
            )
        else:
            orchestrator_rows = self._backfill_orchestrator_seq(read_jsonl(paths["orchestrator"]))
            rows = self._filter_valid_orchestrator_rows(
                rows=orchestrator_rows,
                context=context,
            )

        filtered = self._filter_events(
            rows=rows,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if normalized_stream in {"fcmp", "rasp"} and not terminal_status:
            filtered = self._merge_protocol_rows(
                stream=normalized_stream,
                audit_rows=filtered,
                live_rows=live_rows,
            )
        filtered = self._apply_protocol_limit(
            rows=filtered,
            limit=limit,
            from_seq=from_seq,
            to_seq=to_seq,
        )
        return {
            "attempt": selected_attempt,
            "available_attempts": self._list_available_attempts(run_dir),
            "events": filtered,
            "source": (
                "audit"
                if terminal_status and normalized_stream in {"fcmp", "rasp"}
                else (
                    "mixed"
                    if filtered and live_rows and needs_audit
                    else ("live" if live_rows and not needs_audit else "audit")
                )
            ),
            "cursor_floor": live_floor,
            "cursor_ceiling": live_ceiling,
        }

    def _apply_protocol_limit(
        self,
        *,
        rows: list[dict[str, Any]],
        limit: Optional[int],
        from_seq: Optional[int],
        to_seq: Optional[int],
    ) -> list[dict[str, Any]]:
        if limit is None:
            return rows
        safe_limit = max(1, min(1000, int(limit)))
        if not rows:
            return rows
        if from_seq is not None:
            return rows[:safe_limit]
        if to_seq is not None:
            return rows[-safe_limit:]
        return rows[-safe_limit:]

    async def list_timeline_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        cursor: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        safe_cursor = max(0, int(cursor))
        safe_limit = max(1, min(500, int(limit)))
        status_payload = self._read_status_payload(run_dir)
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        runtime_attempt = await self._resolve_attempt_number(
            request_id=request_id,
            status=status,
            run_dir=run_dir,
            requested_attempt=None,
        )
        attempts = self._list_available_attempts(run_dir)
        if runtime_attempt > 0 and runtime_attempt not in attempts:
            attempts.append(runtime_attempt)
            attempts.sort()
        if not attempts:
            attempts = [runtime_attempt] if runtime_attempt > 0 else [1]

        signature = self._timeline_cache_signature(run_dir=run_dir, attempts=attempts)
        cache_key = str(run_dir.resolve(strict=False))
        cached = self._timeline_cache.get(cache_key)
        if cached is not None and cached.get("signature") == signature:
            all_events_obj = cached.get("events")
            all_events = all_events_obj if isinstance(all_events_obj, list) else []
            if safe_cursor <= 0:
                events = all_events[-safe_limit:]
            else:
                events = [event for event in all_events if int(event.get("timeline_seq") or 0) > safe_cursor][:safe_limit]
            cursor_ceiling = int(all_events[-1]["timeline_seq"]) if all_events else 0
            cursor_floor = int(events[0]["timeline_seq"]) if events else 0
            return {
                "events": events,
                "cursor_floor": cursor_floor,
                "cursor_ceiling": cursor_ceiling,
                "source": "cached",
            }

        protocol_rows: Dict[str, Dict[int, List[Dict[str, Any]]]] = {"orchestrator": {}, "rasp": {}, "fcmp": {}}
        for stream in ("orchestrator", "rasp", "fcmp"):
            for attempt in attempts:
                payload = await self.list_protocol_history(
                    run_dir=run_dir,
                    request_id=request_id,
                    stream=stream,
                    from_seq=None,
                    to_seq=None,
                    from_ts=None,
                    to_ts=None,
                    attempt=attempt,
                    limit=TIMELINE_PROTOCOL_WINDOW_LIMIT,
                )
                rows_obj = payload.get("events")
                protocol_rows[stream][attempt] = rows_obj if isinstance(rows_obj, list) else []

        chat_payload = await self.get_chat_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=None,
            to_seq=None,
            from_ts=None,
            to_ts=None,
        )
        chat_rows_obj = chat_payload.get("events")
        chat_rows = chat_rows_obj if isinstance(chat_rows_obj, list) else []

        timeline_index = 0
        collected: List[Dict[str, Any]] = []

        def _collect(
            *,
            lane: str,
            kind: str,
            summary: str,
            attempt_number: int,
            source_stream: str,
            ts: str,
            seq_like: int,
            details: Dict[str, Any],
            raw_ref: Optional[Dict[str, Any]] = None,
        ) -> None:
            nonlocal timeline_index
            timeline_index += 1
            event: Dict[str, Any] = {
                "timeline_seq": 0,
                "ts": ts,
                "lane": lane,
                "kind": kind,
                "summary": summary,
                "attempt": attempt_number,
                "source_stream": source_stream,
                "details": details,
            }
            if raw_ref is not None:
                event["raw_ref"] = raw_ref
            collected.append(
                {
                    "event": event,
                    "ts_value": self._timeline_ts_value(ts),
                    "attempt": attempt_number if attempt_number > 0 else 0,
                    "stream_priority": TIMELINE_STREAM_PRIORITY.get(source_stream, 9),
                    "seq_like": max(0, int(seq_like)),
                    "ingest_index": timeline_index,
                }
            )

        for stream in ("orchestrator", "rasp", "fcmp"):
            for attempt in attempts:
                for row in protocol_rows[stream].get(attempt, []):
                    if not isinstance(row, dict):
                        continue
                    ts = self._timeline_ts_text(row.get("ts"))
                    kind = self._timeline_kind_from_row(row)
                    summary = self._timeline_protocol_summary(stream, row)
                    seq_like = self._timeline_seq_like(row)
                    raw_ref = self._timeline_extract_raw_ref(row, fallback_attempt=attempt)
                    _collect(
                        lane=TIMELINE_LANE_BY_STREAM[stream],
                        kind=kind,
                        summary=summary,
                        attempt_number=attempt,
                        source_stream=stream,
                        ts=ts,
                        seq_like=seq_like,
                        details={"stream": stream, "event": row},
                        raw_ref=raw_ref,
                    )
                    if stream == "fcmp" and kind in {"interaction.reply.accepted", "auth.input.accepted"}:
                        _collect(
                            lane=TIMELINE_LANE_BY_STREAM["client"],
                            kind=kind,
                            summary=self._timeline_client_summary_from_fcmp(row),
                            attempt_number=attempt,
                            source_stream="client",
                            ts=ts,
                            seq_like=seq_like,
                            details={"source": "fcmp", "event": row},
                            raw_ref=raw_ref,
                        )

        for row in chat_rows:
            if not isinstance(row, dict):
                continue
            ts = self._timeline_ts_text(row.get("created_at"))
            attempt_number = self._timeline_attempt_number(
                row.get("attempt"),
                fallback=self._timeline_attempt_number(
                    (row.get("correlation") or {}).get("source_attempt"),
                    fallback=runtime_attempt,
                ),
            )
            seq_like = self._timeline_seq_like(row)
            kind_obj = row.get("kind")
            kind = kind_obj if isinstance(kind_obj, str) and kind_obj else "chat.message"
            summary = self._timeline_chat_summary(row)
            raw_ref = self._timeline_extract_raw_ref(row, fallback_attempt=attempt_number)
            _collect(
                lane=TIMELINE_LANE_BY_STREAM["chat"],
                kind=kind,
                summary=summary,
                attempt_number=attempt_number,
                source_stream="chat",
                ts=ts,
                seq_like=seq_like,
                details={"stream": "chat", "event": row},
                raw_ref=raw_ref,
            )
            if row.get("role") == "user":
                _collect(
                    lane=TIMELINE_LANE_BY_STREAM["client"],
                    kind="client.user_message",
                    summary=self._timeline_client_summary_from_chat(row),
                    attempt_number=attempt_number,
                    source_stream="client",
                    ts=ts,
                    seq_like=seq_like,
                    details={"source": "chat", "event": row},
                    raw_ref=raw_ref,
                )

        collected.sort(
            key=lambda item: (
                0 if item["ts_value"] is not None else 1,
                item["ts_value"] if item["ts_value"] is not None else float("inf"),
                item["attempt"],
                item["stream_priority"],
                item["seq_like"],
                item["ingest_index"],
            )
        )
        for index, item in enumerate(collected, start=1):
            item["event"]["timeline_seq"] = index

        all_events = [item["event"] for item in collected]
        self._set_timeline_cache(cache_key=cache_key, signature=signature, events=all_events)
        if safe_cursor <= 0:
            events = all_events[-safe_limit:]
        else:
            events = [event for event in all_events if int(event.get("timeline_seq") or 0) > safe_cursor][:safe_limit]
        cursor_ceiling = int(all_events[-1]["timeline_seq"]) if all_events else 0
        cursor_floor = int(events[0]["timeline_seq"]) if events else 0
        return {
            "events": events,
            "cursor_floor": cursor_floor,
            "cursor_ceiling": cursor_ceiling,
            "source": "mixed",
        }

    def _timeline_cache_signature(self, *, run_dir: Path, attempts: list[int]) -> tuple[Any, ...]:
        parts: list[tuple[str, int, int]] = []
        for attempt in attempts:
            paths = self._protocol_paths(run_dir, attempt)
            for key in ("orchestrator", "events", "fcmp"):
                path = paths[key]
                if path.exists() and path.is_file():
                    stat = path.stat()
                    parts.append((path.name, int(stat.st_size), int(stat.st_mtime_ns)))
                else:
                    parts.append((path.name, -1, -1))
        chat_path = run_dir / AUDIT_DIR_NAME / "chat_replay.jsonl"
        if chat_path.exists() and chat_path.is_file():
            stat = chat_path.stat()
            parts.append((chat_path.name, int(stat.st_size), int(stat.st_mtime_ns)))
        else:
            parts.append((chat_path.name, -1, -1))
        return tuple(parts)

    def _set_timeline_cache(self, *, cache_key: str, signature: tuple[Any, ...], events: list[dict[str, Any]]) -> None:
        self._timeline_cache[cache_key] = {"signature": signature, "events": events}
        if cache_key in self._timeline_cache_order:
            self._timeline_cache_order.remove(cache_key)
        self._timeline_cache_order.append(cache_key)
        while len(self._timeline_cache_order) > TIMELINE_CACHE_MAX_ENTRIES:
            stale = self._timeline_cache_order.pop(0)
            self._timeline_cache.pop(stale, None)

    def _timeline_ts_text(self, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return ""

    def _timeline_ts_value(self, value: str) -> Optional[float]:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed.timestamp()

    def _timeline_attempt_number(self, value: Any, *, fallback: int = 0) -> int:
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str):
            try:
                parsed = int(value.strip())
            except ValueError:
                parsed = 0
            if parsed > 0:
                return parsed
        return max(0, int(fallback))

    def _timeline_seq_like(self, row: Dict[str, Any]) -> int:
        seq_obj = row.get("seq")
        if isinstance(seq_obj, int):
            return max(0, seq_obj)
        local_seq_obj = ((row.get("meta") or {}).get("local_seq"))
        if isinstance(local_seq_obj, int):
            return max(0, local_seq_obj)
        return 0

    def _timeline_kind_from_row(self, row: Dict[str, Any]) -> str:
        for key in ("type", "event_type", "event", "kind"):
            value = row.get(key)
            if isinstance(value, str) and value:
                return value
            if key == "event" and isinstance(value, dict):
                nested_type = value.get("type")
                if isinstance(nested_type, str) and nested_type:
                    return nested_type
        return "event"

    def _timeline_protocol_summary(self, stream: str, row: Dict[str, Any]) -> str:
        kind = self._timeline_kind_from_row(row)
        payload_obj = row.get("payload")
        payload: Dict[str, Any] = {}
        if isinstance(payload_obj, dict):
            payload = payload_obj
        else:
            data_obj = row.get("data")
            if isinstance(data_obj, dict):
                payload = data_obj
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            normalized = " ".join(message.split())
            return normalized[:220] + ("..." if len(normalized) > 220 else "")
        if stream == "rasp":
            source_obj = row.get("source")
            source = source_obj if isinstance(source_obj, dict) else {}
            engine = source.get("engine") if isinstance(source.get("engine"), str) else "unknown"
            parser = source.get("parser") if isinstance(source.get("parser"), str) else "unknown"
            code = payload.get("code") if isinstance(payload.get("code"), str) else ""
            status = payload.get("status") if isinstance(payload.get("status"), str) else ""
            parts = [f"{kind}", f"{engine}/{parser}"]
            if code:
                parts.append(f"code={code}")
            if status:
                parts.append(f"status={status}")
            return " · ".join(parts)
        if kind == "conversation.state.changed":
            from_state = payload.get("from")
            to_state = payload.get("to")
            from_text = from_state if isinstance(from_state, str) and from_state else "?"
            to_text = to_state if isinstance(to_state, str) and to_state else "?"
            return f"state: {from_text} -> {to_text}"
        status = payload.get("status")
        if isinstance(status, str) and status:
            return f"{kind} ({status})"
        return kind

    def _timeline_chat_summary(self, row: Dict[str, Any]) -> str:
        role = row.get("role") if isinstance(row.get("role"), str) else "chat"
        text_obj = row.get("text")
        if isinstance(text_obj, str) and text_obj.strip():
            normalized = " ".join(text_obj.split())
            preview = normalized[:180] + ("..." if len(normalized) > 180 else "")
            return f"{role}: {preview}"
        kind_obj = row.get("kind")
        kind = kind_obj if isinstance(kind_obj, str) and kind_obj else "chat.message"
        return f"{role}: {kind}"

    def _timeline_client_summary_from_chat(self, row: Dict[str, Any]) -> str:
        text_obj = row.get("text")
        if isinstance(text_obj, str) and text_obj.strip():
            normalized = " ".join(text_obj.split())
            return normalized[:180] + ("..." if len(normalized) > 180 else "")
        return "Client message submitted"

    def _timeline_client_summary_from_fcmp(self, row: Dict[str, Any]) -> str:
        kind = self._timeline_kind_from_row(row)
        payload_obj = row.get("payload")
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        if kind == "interaction.reply.accepted":
            response = payload.get("response")
            if isinstance(response, dict):
                text_obj = response.get("text")
                if isinstance(text_obj, str) and text_obj.strip():
                    normalized = " ".join(text_obj.split())
                    return f"Reply accepted: {normalized[:140]}{'...' if len(normalized) > 140 else ''}"
            return "Interaction reply accepted"
        if kind == "auth.input.accepted":
            submission_kind = payload.get("submission_kind")
            if isinstance(submission_kind, str) and submission_kind:
                return f"Auth input accepted: {submission_kind}"
            return "Auth input accepted"
        return kind

    def _timeline_extract_raw_ref(
        self,
        row: Dict[str, Any],
        *,
        fallback_attempt: int,
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Any] = []
        candidates.append(row.get("raw_ref"))
        meta_obj = row.get("meta")
        if isinstance(meta_obj, dict):
            candidates.append(meta_obj.get("raw_ref"))
        correlation_obj = row.get("correlation")
        if isinstance(correlation_obj, dict):
            candidates.append(correlation_obj.get("raw_ref"))
            candidates.append(correlation_obj)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            stream_obj = candidate.get("stream")
            byte_from_obj = candidate.get("byte_from")
            byte_to_obj = candidate.get("byte_to")
            if not isinstance(stream_obj, str) or not stream_obj:
                continue
            if not isinstance(byte_from_obj, (int, float, str)) or not isinstance(byte_to_obj, (int, float, str)):
                continue
            try:
                byte_from = int(byte_from_obj)
                byte_to = int(byte_to_obj)
            except (TypeError, ValueError):
                continue
            attempt_number = self._timeline_attempt_number(
                candidate.get("attempt_number"),
                fallback=fallback_attempt,
            )
            return {
                "attempt_number": attempt_number,
                "stream": stream_obj,
                "byte_from": max(0, byte_from),
                "byte_to": max(0, byte_to),
            }
        return None

    def _get_live_protocol_payload(
        self,
        *,
        run_dir: Path,
        stream: str,
        attempt_number: int,
        from_seq: Optional[int],
        to_seq: Optional[int],
        from_ts: Optional[str],
        to_ts: Optional[str],
    ) -> Dict[str, Any]:
        run_id = run_dir.name
        after_seq = max(0, int(from_seq or 1) - 1)
        if stream == "fcmp":
            payload = fcmp_live_journal.replay(
                run_id=run_id,
                after_seq=after_seq,
                event_filter=lambda row: int(((row.get("meta") or {}).get("attempt") or 0)) == attempt_number,
            )
        elif stream == "rasp":
            payload = rasp_live_journal.replay(
                run_id=run_id,
                after_seq=after_seq,
                event_filter=lambda row: int(row.get("attempt_number") or 0) == attempt_number,
            )
        else:
            return {"events": [], "cursor_floor": 0, "cursor_ceiling": 0}
        rows = self._filter_events(
            rows=payload.get("events", []),
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        return {
            "events": rows,
            "cursor_floor": payload.get("cursor_floor", 0),
            "cursor_ceiling": payload.get("cursor_ceiling", 0),
        }

    def _protocol_row_stable_key(self, *, stream: str, row: Dict[str, Any]) -> str:
        if stream == "rasp":
            attempt_obj = row.get("attempt_number")
            attempt = int(attempt_obj) if isinstance(attempt_obj, int) else 0
            event_obj = row.get("event")
            event = event_obj if isinstance(event_obj, dict) else {}
            type_name = str(event.get("type") or row.get("type") or "")
            category = str(event.get("category") or row.get("category") or "")
            raw_ref_obj = row.get("raw_ref")
            raw_ref = raw_ref_obj if isinstance(raw_ref_obj, dict) else {}
            stream_name = str(raw_ref.get("stream") or "")
            byte_from = raw_ref.get("byte_from")
            byte_to = raw_ref.get("byte_to")
            if stream_name and isinstance(byte_from, int) and isinstance(byte_to, int):
                return (
                    f"rasp:{attempt}:{category}:{type_name}:{stream_name}:"
                    f"{byte_from}:{byte_to}"
                )
            seq_obj = row.get("seq")
            seq = int(seq_obj) if isinstance(seq_obj, int) else 0
            ts = str(row.get("ts") or "")
            return f"rasp:fallback:{attempt}:{category}:{type_name}:{seq}:{ts}"
        seq_obj = row.get("seq")
        if isinstance(seq_obj, int):
            return f"{stream}:seq:{seq_obj}"
        ts = str(row.get("ts") or "")
        type_name = str(row.get("type") or "")
        try:
            fingerprint = json.dumps(row, sort_keys=True, ensure_ascii=False)
        except TypeError:
            fingerprint = repr(row)
        return f"{stream}:fallback:{type_name}:{ts}:{fingerprint}"

    def _protocol_sort_key(self, row: Dict[str, Any]) -> tuple[int, str]:
        seq_obj = row.get("seq")
        seq = int(seq_obj) if isinstance(seq_obj, int) else 0
        ts = str(row.get("ts") or "")
        return (seq, ts)

    def _merge_protocol_rows(
        self,
        *,
        stream: str,
        audit_rows: List[Dict[str, Any]],
        live_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for row in audit_rows:
            merged[self._protocol_row_stable_key(stream=stream, row=row)] = row
        for row in live_rows:
            key = self._protocol_row_stable_key(stream=stream, row=row)
            if key not in merged:
                merged[key] = row
        return sorted(merged.values(), key=self._protocol_sort_key)

    def reindex_fcmp_global_seq(self, run_dir: Path) -> None:
        attempts = self._list_available_attempts(run_dir)
        if not attempts:
            return
        next_global_seq = 1
        for attempt_number in attempts:
            path = self._protocol_paths(run_dir, attempt_number)["fcmp"]
            rows = read_jsonl(path)
            if not rows:
                continue
            rewritten: List[Dict[str, Any]] = []
            for local_seq, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                row_copy = dict(row)
                meta_obj = row_copy.get("meta")
                meta = dict(meta_obj) if isinstance(meta_obj, dict) else {}
                meta["attempt"] = attempt_number
                meta["local_seq"] = local_seq
                row_copy["meta"] = meta
                row_copy["seq"] = next_global_seq
                next_global_seq += 1
                try:
                    validate_fcmp_event(row_copy)
                except ProtocolSchemaViolation as exc:
                    logger.warning(
                        "Skip invalid FCMP row during global reindex: run=%s attempt=%s local_seq=%s detail=%s",
                        run_dir.name,
                        attempt_number,
                        local_seq,
                        str(exc),
                    )
                    continue
                rewritten.append(row_copy)
            write_jsonl(path, rewritten)

    def _ensure_global_fcmp_seq(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        expected = 1
        for row in rows:
            seq_obj = row.get("seq")
            if not isinstance(seq_obj, int) or seq_obj != expected:
                return self._with_global_fcmp_seq(rows)
            expected += 1
        return rows

    def _with_global_fcmp_seq(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        remapped: List[Dict[str, Any]] = []
        local_seq_counters: Dict[int, int] = {}
        for index, row in enumerate(rows, start=1):
            row_copy = dict(row)
            meta_obj = row.get("meta")
            meta = dict(meta_obj) if isinstance(meta_obj, dict) else {}
            attempt_obj = meta.get("attempt")
            attempt_number = int(attempt_obj) if isinstance(attempt_obj, int) and attempt_obj > 0 else 0
            local_seq_counters[attempt_number] = local_seq_counters.get(attempt_number, 0) + 1
            local_seq_obj = meta.get("local_seq")
            local_seq = (
                int(local_seq_obj)
                if isinstance(local_seq_obj, int) and local_seq_obj > 0
                else 0
            )
            if local_seq <= 0:
                seq_obj = row.get("seq")
                if isinstance(seq_obj, int) and seq_obj > 0:
                    local_seq = seq_obj
                else:
                    local_seq = local_seq_counters[attempt_number]
            meta["local_seq"] = local_seq
            row_copy["meta"] = meta
            row_copy["seq"] = index
            remapped.append(row_copy)
        return remapped

    def _backfill_orchestrator_seq(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        backfilled: List[Dict[str, Any]] = []
        next_seq = 1
        for row in rows:
            if not isinstance(row, dict):
                continue
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int) and seq_obj > 0:
                next_seq = max(next_seq, seq_obj + 1)
                backfilled.append(row)
                continue
            row_copy = dict(row)
            row_copy["seq"] = next_seq
            next_seq += 1
            backfilled.append(row_copy)
        return backfilled

    def _protocol_paths(self, run_dir: Path, attempt_number: int) -> Dict[str, Path]:
        audit_dir = run_dir / AUDIT_DIR_NAME
        suffix = f".{attempt_number}"
        return {
            "audit_dir": audit_dir,
            "events": audit_dir / f"{RASP_EVENTS_FILE_PREFIX}{suffix}.jsonl",
            "diagnostics": audit_dir / f"{PARSER_DIAGNOSTICS_FILE_PREFIX}{suffix}.jsonl",
            "fcmp": audit_dir / f"{FCMP_EVENTS_FILE_PREFIX}{suffix}.jsonl",
            "metrics": audit_dir / f"{PROTOCOL_METRICS_FILE_PREFIX}{suffix}.json",
            "orchestrator": audit_dir / f"{ORCHESTRATOR_EVENTS_FILE_PREFIX}{suffix}.jsonl",
            "io_chunks": audit_dir / f"{IO_CHUNKS_FILE_PREFIX}{suffix}.jsonl",
        }

    def _decode_io_chunks(
        self,
        *,
        io_chunks_path: Path,
    ) -> Dict[str, Any]:
        if not io_chunks_path.exists() or not io_chunks_path.is_file():
            return {"used": False, "reason": "missing", "stdout_raw": None, "stderr_raw": None, "diagnostics": []}
        rows = read_jsonl(io_chunks_path)
        if not rows:
            return {"used": False, "reason": "empty", "stdout_raw": None, "stderr_raw": None, "diagnostics": []}
        ordered: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                row_copy = dict(row)
                row_copy["_index"] = index
                ordered.append(row_copy)
        if not ordered:
            return {"used": False, "reason": "invalid_rows", "stdout_raw": None, "stderr_raw": None, "diagnostics": []}
        ordered.sort(
            key=lambda item: (
                int(item["seq"]) if isinstance(item.get("seq"), int) and int(item["seq"]) > 0 else 10**12,
                int(item.get("_index") or 0),
            )
        )
        stdout = bytearray()
        stderr = bytearray()
        diagnostics: list[str] = []
        decode_count = 0
        for row in ordered:
            stream_obj = row.get("stream")
            if stream_obj not in {"stdout", "stderr"}:
                diagnostics.append("IO_CHUNK_UNKNOWN_STREAM")
                continue
            payload_b64_obj = row.get("payload_b64")
            if not isinstance(payload_b64_obj, str) or not payload_b64_obj:
                diagnostics.append("IO_CHUNK_MISSING_PAYLOAD")
                continue
            try:
                payload = base64.b64decode(payload_b64_obj, validate=True)
            except (binascii.Error, ValueError):
                diagnostics.append("IO_CHUNK_INVALID_BASE64")
                continue
            target = stdout if stream_obj == "stdout" else stderr
            byte_from_obj = row.get("byte_from")
            if isinstance(byte_from_obj, int) and byte_from_obj >= 0 and byte_from_obj != len(target):
                diagnostics.append("IO_CHUNK_OFFSET_MISMATCH")
            byte_to_obj = row.get("byte_to")
            if isinstance(byte_from_obj, int) and isinstance(byte_to_obj, int):
                expected = byte_from_obj + len(payload)
                if byte_to_obj != expected:
                    diagnostics.append("IO_CHUNK_RANGE_MISMATCH")
            target.extend(payload)
            decode_count += 1
        if decode_count <= 0:
            return {"used": False, "reason": "decode_failed", "stdout_raw": None, "stderr_raw": None, "diagnostics": diagnostics}
        return {
            "used": True,
            "reason": "io_chunks",
            "stdout_raw": bytes(stdout),
            "stderr_raw": bytes(stderr),
            "diagnostics": diagnostics,
        }

    def _backup_protocol_attempt_files(
        self,
        *,
        paths: Dict[str, Path],
        backup_attempt_dir: Path,
    ) -> None:
        backup_attempt_dir.mkdir(parents=True, exist_ok=True)
        for key in ("events", "fcmp", "diagnostics", "metrics", "orchestrator"):
            source = paths.get(key)
            if source is None or not source.exists() or not source.is_file():
                continue
            shutil.copy2(source, backup_attempt_dir / source.name)

    def _atomic_write_jsonl(self, *, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        write_jsonl(temp_path, rows)
        temp_path.replace(path)

    def _atomic_write_text(self, *, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)

    def _load_io_chunks_for_strict_replay(
        self,
        *,
        io_chunks_path: Path,
    ) -> Dict[str, Any]:
        if not io_chunks_path.exists() or not io_chunks_path.is_file():
            return {"used": False, "reason": "missing", "rows": [], "diagnostics": []}
        rows = read_jsonl(io_chunks_path)
        if not rows:
            return {"used": False, "reason": "empty", "rows": [], "diagnostics": []}
        ordered: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            row_copy = dict(row)
            row_copy["_index"] = index
            ordered.append(row_copy)
        if not ordered:
            return {"used": False, "reason": "invalid_rows", "rows": [], "diagnostics": []}
        ordered.sort(
            key=lambda item: (
                int(item["seq"]) if isinstance(item.get("seq"), int) and int(item["seq"]) > 0 else 10**12,
                int(item.get("_index") or 0),
            )
        )
        diagnostics: list[str] = []
        replay_rows: list[dict[str, Any]] = []
        for row in ordered:
            seq_obj = row.get("seq")
            seq = seq_obj if isinstance(seq_obj, int) and seq_obj > 0 else None
            stream_obj = row.get("stream")
            stream = stream_obj if isinstance(stream_obj, str) and stream_obj in {"stdout", "stderr"} else None
            payload_b64_obj = row.get("payload_b64")
            payload_b64 = payload_b64_obj if isinstance(payload_b64_obj, str) and payload_b64_obj else None
            if seq is None or stream is None or payload_b64 is None:
                diagnostics.append("IO_CHUNK_ROW_INVALID")
                continue
            try:
                payload = base64.b64decode(payload_b64, validate=True)
            except (binascii.Error, ValueError):
                diagnostics.append("IO_CHUNK_INVALID_BASE64")
                continue
            byte_from_obj = row.get("byte_from")
            byte_to_obj = row.get("byte_to")
            byte_from = byte_from_obj if isinstance(byte_from_obj, int) and byte_from_obj >= 0 else 0
            expected_to = byte_from + len(payload)
            if isinstance(byte_to_obj, int) and byte_to_obj >= byte_from:
                byte_to = byte_to_obj
                if byte_to != expected_to:
                    diagnostics.append("IO_CHUNK_RANGE_MISMATCH")
            else:
                byte_to = expected_to
            ts_obj = row.get("ts")
            ts = ts_obj if isinstance(ts_obj, str) and ts_obj else None
            replay_rows.append(
                {
                    "seq": seq,
                    "ts": ts,
                    "stream": stream,
                    "byte_from": byte_from,
                    "byte_to": byte_to,
                    "text": payload.decode("utf-8", errors="replace"),
                }
            )
        if not replay_rows:
            return {"used": False, "reason": "decode_failed", "rows": [], "diagnostics": diagnostics}
        return {
            "used": True,
            "reason": "io_chunks",
            "rows": replay_rows,
            "diagnostics": diagnostics,
        }

    async def _strict_replay_attempt(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        engine_name: str,
        attempt_number: int,
        paths: Dict[str, Path],
        attempt_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        io_chunks_decode = self._load_io_chunks_for_strict_replay(io_chunks_path=paths["io_chunks"])
        if not bool(io_chunks_decode.get("used")):
            reason_obj = io_chunks_decode.get("reason")
            reason = reason_obj if isinstance(reason_obj, str) and reason_obj else "unknown"
            return {
                "success": False,
                "written": False,
                "reason": f"IO_CHUNKS_REQUIRED:{reason}",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        if not paths["orchestrator"].exists() or not paths["orchestrator"].is_file():
            return {
                "success": False,
                "written": False,
                "reason": "ORCHESTRATOR_REQUIRED:missing",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        if not attempt_meta:
            return {
                "success": False,
                "written": False,
                "reason": "META_REQUIRED:missing",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        if parser_resolver is None:
            return {
                "success": False,
                "written": False,
                "reason": "PARSER_RESOLVER_REQUIRED:missing",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        adapter = parser_resolver.resolve(engine_name)
        if adapter is None or not hasattr(adapter, "stream_parser"):
            return {
                "success": False,
                "written": False,
                "reason": "ENGINE_ADAPTER_REQUIRED:missing",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        stream_parser = getattr(adapter, "stream_parser", None)
        if stream_parser is None:
            return {
                "success": False,
                "written": False,
                "reason": "ENGINE_STREAM_PARSER_REQUIRED:missing",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }

        replay_chunks = list(io_chunks_decode.get("rows") or [])
        orchestrator_rows = self._filter_valid_orchestrator_rows(
            rows=read_jsonl(paths["orchestrator"]),
            context=f"strict-replay:{request_id or run_dir.name}:a{attempt_number}",
        )
        process_obj = attempt_meta.get("process")
        process_payload = process_obj if isinstance(process_obj, dict) else {}
        exit_code_obj = process_payload.get("exit_code")
        exit_code = exit_code_obj if isinstance(exit_code_obj, int) else 0
        failure_reason_obj = process_payload.get("failure_reason")
        failure_reason = (
            failure_reason_obj if isinstance(failure_reason_obj, str) and failure_reason_obj else None
        )
        started_at = self._parse_optional_ts(attempt_meta.get("started_at"))
        finished_at = (
            self._parse_optional_ts(attempt_meta.get("finished_at"))
            or self._parse_optional_ts(attempt_meta.get("updated_at"))
        )
        if started_at is None and replay_chunks:
            started_at = self._parse_optional_ts(replay_chunks[0].get("ts"))
        if finished_at is None and replay_chunks:
            finished_at = self._parse_optional_ts(replay_chunks[-1].get("ts"))

        temp_root = run_dir / AUDIT_DIR_NAME / ".strict_replay_tmp"
        temp_run_dir = temp_root / f"attempt-{attempt_number}"
        temp_audit_dir = temp_run_dir / AUDIT_DIR_NAME
        temp_audit_dir.mkdir(parents=True, exist_ok=True)

        fcmp_publisher = FcmpEventPublisher()
        rasp_publisher = RaspEventPublisher()
        emitter = LiveRuntimeEmitterImpl(
            run_id=run_dir.name,
            run_dir=temp_run_dir,
            engine=engine_name,
            attempt_number=attempt_number,
            stream_parser=stream_parser,
            fcmp_publisher=fcmp_publisher,
            rasp_publisher=rasp_publisher,
            run_handle_consumer=None,
        )

        fallback_ts = started_at or finished_at
        timeline: list[tuple[datetime, int, int, str, dict[str, Any]]] = []
        for index, chunk in enumerate(replay_chunks):
            ts = self._parse_optional_ts(chunk.get("ts")) or fallback_ts
            if ts is None:
                shutil.rmtree(temp_root, ignore_errors=True)
                return {
                    "success": False,
                    "written": False,
                    "reason": "TIMESTAMP_EVIDENCE_REQUIRED:io_chunks",
                    "source": "io_chunks",
                    "event_count": 0,
                    "fcmp_count": 0,
                    "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
                }
            timeline.append((ts, 1, index, "chunk", chunk))
        for index, row in enumerate(orchestrator_rows):
            ts = self._parse_optional_ts(row.get("ts")) or fallback_ts
            if ts is None:
                shutil.rmtree(temp_root, ignore_errors=True)
                return {
                    "success": False,
                    "written": False,
                    "reason": "TIMESTAMP_EVIDENCE_REQUIRED:orchestrator",
                    "source": "io_chunks",
                    "event_count": 0,
                    "fcmp_count": 0,
                    "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
                }
            timeline.append((ts, 0, index, "orchestrator", row))
        if started_at is None and timeline:
            started_at = timeline[0][0]
        if finished_at is None and timeline:
            finished_at = timeline[-1][0]
        if started_at is None or finished_at is None:
            shutil.rmtree(temp_root, ignore_errors=True)
            return {
                "success": False,
                "written": False,
                "reason": "TIMESTAMP_EVIDENCE_REQUIRED:meta",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }
        timeline.sort(key=lambda item: (item[0], item[1], item[2]))

        await emitter.on_process_started(event_ts=started_at)
        for ts, _priority, _index, item_kind, payload in timeline:
            if item_kind == "orchestrator":
                type_name_obj = payload.get("type")
                row_data_obj = payload.get("data")
                if not isinstance(type_name_obj, str):
                    continue
                row_data = row_data_obj if isinstance(row_data_obj, dict) else {}
                specs = translate_orchestrator_event_to_fcmp_specs(
                    engine=engine_name,
                    type_name=type_name_obj,
                    data=row_data,
                    updated_at=payload.get("ts") if isinstance(payload.get("ts"), str) else None,
                    default_attempt_number=attempt_number,
                )
                for spec in specs:
                    spec_type_obj = spec.get("type_name")
                    spec_data_obj = spec.get("data")
                    if not isinstance(spec_type_obj, str) or not isinstance(spec_data_obj, dict):
                        continue
                    fcmp_event = make_fcmp_event(
                        run_id=run_dir.name,
                        seq=1,
                        engine=engine_name,
                        type_name=spec_type_obj,
                        data=spec_data_obj,
                        attempt_number=attempt_number,
                        raw_ref=None,
                        ts=ts,
                    )
                    fcmp_publisher.publish(run_dir=temp_run_dir, event=fcmp_event)
                continue
            await emitter.on_stream_chunk(
                stream=str(payload.get("stream") or "stdout"),
                text=str(payload.get("text") or ""),
                byte_from=max(0, int(payload.get("byte_from") or 0)),
                byte_to=max(0, int(payload.get("byte_to") or 0)),
                event_ts=ts,
            )
        await emitter.on_process_exit(
            exit_code=exit_code,
            failure_reason=failure_reason,
            event_ts=finished_at,
        )
        await asyncio.gather(
            fcmp_publisher.drain_mirror(run_id=run_dir.name),
            rasp_publisher.drain_mirror(run_id=run_dir.name),
        )

        temp_events_path = temp_audit_dir / f"{RASP_EVENTS_FILE_PREFIX}.{attempt_number}.jsonl"
        temp_fcmp_path = temp_audit_dir / f"{FCMP_EVENTS_FILE_PREFIX}.{attempt_number}.jsonl"
        if not temp_events_path.exists() or not temp_fcmp_path.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
            return {
                "success": False,
                "written": False,
                "reason": "STRICT_REPLAY_OUTPUT_MISSING",
                "source": "io_chunks",
                "event_count": 0,
                "fcmp_count": 0,
                "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
            }

        rasp_rows = self._filter_valid_rasp_rows(
            rows=read_jsonl(temp_events_path),
            context=f"strict-replay:rasp:{request_id or run_dir.name}:a{attempt_number}",
        )
        fcmp_rows = self._filter_valid_fcmp_rows(
            rows=read_jsonl(temp_fcmp_path),
            context=f"strict-replay:fcmp:{request_id or run_dir.name}:a{attempt_number}",
        )
        diagnostics_rows = [
            row
            for row in rasp_rows
            if isinstance(row.get("event"), dict) and row["event"].get("category") == "diagnostic"
        ]
        from server.models import RuntimeEventEnvelope  # local import to avoid runtime cycles

        rasp_models = [RuntimeEventEnvelope.model_validate(row) for row in rasp_rows]
        metrics_payload = compute_protocol_metrics(rasp_models)

        metrics_text = json.dumps(metrics_payload, ensure_ascii=False, indent=2)
        self._atomic_write_jsonl(path=paths["events"], rows=rasp_rows)
        self._atomic_write_jsonl(path=paths["fcmp"], rows=fcmp_rows)
        self._atomic_write_jsonl(path=paths["diagnostics"], rows=diagnostics_rows)
        self._atomic_write_text(path=paths["metrics"], text=metrics_text)
        self.reindex_fcmp_global_seq(run_dir)
        shutil.rmtree(temp_root, ignore_errors=True)
        return {
            "success": True,
            "written": True,
            "reason": "OK",
            "source": "io_chunks",
            "event_count": len(rasp_rows),
            "fcmp_count": len(fcmp_rows),
            "diagnostics": list(io_chunks_decode.get("diagnostics") or []),
        }

    async def _resolve_engine_name(self, request_id: Optional[str]) -> str:
        if not request_id:
            return "unknown"
        request_record = await maybe_await(self._run_store().get_request(request_id))
        if not request_record:
            return "unknown"
        engine_obj = request_record.get("engine")
        if isinstance(engine_obj, str) and engine_obj:
            return engine_obj
        return "unknown"

    def _latest_attempt_number(self, run_dir: Path) -> int:
        attempts = self._list_available_attempts(run_dir)
        return attempts[-1] if attempts else 0

    def _list_available_attempts(self, run_dir: Path) -> List[int]:
        audit_dir = run_dir / AUDIT_DIR_NAME
        if not audit_dir.exists() or not audit_dir.is_dir():
            return []
        attempts: set[int] = set()
        for path in audit_dir.iterdir():
            if not path.is_file():
                continue
            for pattern in ATTEMPT_FILE_PATTERNS:
                matched = pattern.match(path.name)
                if not matched:
                    continue
                try:
                    value = int(matched.group(1))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    attempts.add(value)
                break
        return sorted(attempts)

    async def _resolve_attempt_number(
        self,
        request_id: Optional[str],
        *,
        status: str,
        run_dir: Path,
        requested_attempt: Optional[int] = None,
    ) -> int:
        available_attempts = self._list_available_attempts(run_dir)
        if requested_attempt is not None:
            requested_value = int(requested_attempt)
            if requested_value <= 0:
                raise ValueError("attempt must be >= 1")
            if available_attempts and requested_value not in available_attempts:
                raise ValueError(f"attempt not found: {requested_value}")
            return requested_value
        if not request_id:
            return available_attempts[-1] if available_attempts else 1
        request_record = await maybe_await(self._run_store().get_request(request_id))
        if not request_record:
            return available_attempts[-1] if available_attempts else 1
        runtime_options = request_record.get(
            "effective_runtime_options",
            request_record.get("runtime_options"),
        )
        execution_mode = ""
        if isinstance(runtime_options, dict):
            execution_mode_obj = runtime_options.get("execution_mode")
            if isinstance(execution_mode_obj, str):
                execution_mode = execution_mode_obj
        if execution_mode != "interactive":
            return available_attempts[-1] if available_attempts else 1
        latest_attempt = self._latest_attempt_number(run_dir)
        if status in {"waiting_user", "succeeded", "failed", "canceled"} and latest_attempt > 0:
            return latest_attempt
        interaction_count = await maybe_await(self._run_store().get_interaction_count(request_id))
        return max(1, int(interaction_count) + 1)

    async def rebuild_protocol_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        rebuild_mode = "strict_replay"
        attempts = self._list_available_attempts(run_dir)
        if not attempts:
            attempts = [1]
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        backup_root = run_dir / AUDIT_DIR_NAME / "rebuild_backups" / timestamp
        engine_name = await self._resolve_engine_name(request_id)
        attempt_results: list[dict[str, Any]] = []
        success = True
        for attempt_number in attempts:
            paths = self._protocol_paths(run_dir, attempt_number)
            backup_attempt_dir = backup_root / f"attempt-{attempt_number}"
            self._backup_protocol_attempt_files(
                paths=paths,
                backup_attempt_dir=backup_attempt_dir,
            )
            attempt_meta = self._read_attempt_meta(paths["audit_dir"], attempt_number)
            attempt_engine_obj = attempt_meta.get("engine")
            attempt_engine = (
                attempt_engine_obj
                if isinstance(attempt_engine_obj, str) and attempt_engine_obj.strip()
                else engine_name
            )
            try:
                replay_result = await self._strict_replay_attempt(
                    run_dir=run_dir,
                    request_id=request_id,
                    engine_name=attempt_engine,
                    attempt_number=attempt_number,
                    paths=paths,
                    attempt_meta=attempt_meta,
                )
                success = success and bool(replay_result.get("success"))
                attempt_results.append(
                    {
                        "attempt": attempt_number,
                        "source": str(replay_result.get("source") or "io_chunks"),
                        "written": bool(replay_result.get("written")),
                        "reason": str(replay_result.get("reason") or "UNKNOWN"),
                        "event_count": int(replay_result.get("event_count") or 0),
                        "fcmp_count": int(replay_result.get("fcmp_count") or 0),
                        "diagnostics": list(replay_result.get("diagnostics") or []),
                        "mode": rebuild_mode,
                        "success": bool(replay_result.get("success")),
                    }
                )
            except (OSError, RuntimeError, ValueError, ProtocolSchemaViolation, json.JSONDecodeError) as exc:
                success = False
                attempt_results.append(
                    {
                        "attempt": attempt_number,
                        "source": "failed",
                        "written": False,
                        "reason": f"STRICT_REPLAY_FAILED:{type(exc).__name__}",
                        "event_count": 0,
                        "fcmp_count": 0,
                        "diagnostics": [f"REBUILD_FAILED:{type(exc).__name__}"],
                        "mode": rebuild_mode,
                        "success": False,
                        "error": str(exc),
                    }
                )
                logger.exception(
                    "protocol rebuild failed run=%s attempt=%s",
                    run_dir.name,
                    attempt_number,
                )
        return {
            "request_id": request_id,
            "run_id": run_dir.name,
            "mode": rebuild_mode,
            "success": success,
            "backup_dir": str(backup_root),
            "attempts": attempt_results,
        }

    async def _materialize_protocol_stream(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        status_payload: Dict[str, Any],
        attempt_number: Optional[int] = None,
        force_rebuild: bool = False,
        prefer_io_chunks: bool = False,
        rebuild_mode: RebuildMode = "canonical",
    ) -> Dict[str, Any]:
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        run_id = run_dir.name
        engine_name = await self._resolve_engine_name(request_id)
        if attempt_number is None:
            attempt_number = await self._resolve_attempt_number(
                request_id,
                status=status,
                run_dir=run_dir,
            )

        audit_dir = run_dir / AUDIT_DIR_NAME
        attempt_meta = self._read_attempt_meta(audit_dir, attempt_number)
        attempt_status_obj = attempt_meta.get("status")
        if isinstance(attempt_status_obj, str) and attempt_status_obj:
            attempt_status = attempt_status_obj
        elif rebuild_mode == "forensic":
            attempt_status = ""
        else:
            attempt_status = status

        attempted_stdout = audit_dir / f"stdout.{attempt_number}.log"
        attempted_stderr = audit_dir / f"stderr.{attempt_number}.log"
        attempted_pty = audit_dir / f"pty-output.{attempt_number}.log"
        paths = self._protocol_paths(run_dir, attempt_number)
        stdout_path = attempted_stdout
        stderr_path = attempted_stderr
        pty_path = attempted_pty if attempted_pty.exists() else None
        io_chunks_decode = (
            self._decode_io_chunks(io_chunks_path=paths["io_chunks"])
            if prefer_io_chunks
            else {"used": False, "reason": "disabled", "stdout_raw": None, "stderr_raw": None, "diagnostics": []}
        )
        io_chunks_used = bool(io_chunks_decode.get("used"))
        source_mode = "io_chunks" if io_chunks_used else "logs"
        fallback_used = prefer_io_chunks and not io_chunks_used
        rebuild_diagnostics: list[str] = list(io_chunks_decode.get("diagnostics") or [])
        if fallback_used:
            reason_obj = io_chunks_decode.get("reason")
            reason = reason_obj if isinstance(reason_obj, str) and reason_obj else "unknown"
            rebuild_diagnostics.append(f"IO_CHUNKS_FALLBACK:{reason}")

        # Strict audit-only mode: never fallback to legacy run_dir/logs.
        if not io_chunks_used and not stdout_path.exists() and not stderr_path.exists() and pty_path is None:
            warning_payload = {
                "ts": datetime.utcnow().isoformat(),
                "event": {"category": "diagnostic", "type": "diagnostic.warning"},
                "data": {
                    "code": "ATTEMPT_AUDIT_LOG_MISSING",
                    "attempt_number": attempt_number,
                },
            }
            write_jsonl(paths["events"], [])
            write_jsonl(paths["fcmp"], [])
            write_jsonl(paths["diagnostics"], [warning_payload])
            self.reindex_fcmp_global_seq(run_dir)
            paths["metrics"].parent.mkdir(parents=True, exist_ok=True)
            paths["metrics"].write_text(
                json.dumps(
                    {
                        "event_count": 0,
                        "diagnostic_count": 1,
                        "parser_warning_count": 1,
                        "raw_count": 0,
                        "confidence_avg": None,
                        "confidence_min": None,
                        "confidence_max": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            logger.warning(
                "Attempt audit logs missing for %s attempt=%s; skip materialization until logs arrive",
                request_id or run_id,
                attempt_number,
            )
            return {
                "rasp_events": [],
                "fcmp_events": [],
                "source_mode": source_mode,
                "fallback_used": fallback_used,
                "rebuild_diagnostics": rebuild_diagnostics,
            }
        completion_obj = attempt_meta.get("completion")
        completion_payload: Optional[Dict[str, Any]] = (
            completion_obj if isinstance(completion_obj, dict) else None
        )
        interaction_history = (
            await maybe_await(self._run_store().list_interaction_history(request_id))
            if request_id
            else []
        )
        pending_interaction = await self._resolve_attempt_pending_interaction(
            request_id=request_id,
            attempt_number=attempt_number,
            attempt_status=attempt_status,
            interaction_history=interaction_history,
        )
        pending_auth = await self._resolve_attempt_pending_auth(
            request_id=request_id,
            attempt_status=attempt_status,
        )
        pending_auth_method_selection = await self._resolve_attempt_pending_auth_method_selection(
            request_id=request_id,
            attempt_status=attempt_status,
        )
        orchestrator_events = self._filter_valid_orchestrator_rows(
            rows=read_jsonl(self._protocol_paths(run_dir, attempt_number)["orchestrator"]),
            context=f"materialize:{request_id or run_id}",
        )
        existing_fcmp_rows = (
            []
            if force_rebuild
            else self._filter_valid_fcmp_rows(
                rows=read_jsonl(paths["fcmp"]),
                context=f"materialize-existing:{request_id or run_id}",
            )
        )
        status_updated_at_obj = (
            attempt_meta.get("finished_at")
            or attempt_meta.get("updated_at")
            or status_payload.get("updated_at")
        )
        status_updated_at = (
            status_updated_at_obj
            if isinstance(status_updated_at_obj, str) and status_updated_at_obj
            else None
        )
        effective_session_timeout_sec = (
            await maybe_await(self._run_store().get_effective_session_timeout(request_id))
            if request_id
            else None
        )

        rasp_models = build_rasp_events(
            run_id=run_id,
            engine=engine_name,
            attempt_number=attempt_number,
            status=attempt_status,
            pending_interaction=pending_interaction,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            pty_path=pty_path,
            stdout_raw=io_chunks_decode.get("stdout_raw"),
            stderr_raw=io_chunks_decode.get("stderr_raw"),
            completion=completion_payload,
            parser_resolver=parser_resolver,
            rebuild_mode=rebuild_mode,
        )
        rasp_rows = [model.model_dump(mode="json") for model in rasp_models]
        for row in rasp_rows:
            validate_rasp_event(row)
        if existing_fcmp_rows:
            fcmp_rows = existing_fcmp_rows
        else:
            fcmp_models = build_fcmp_events(
                rasp_models,
                status=attempt_status,
                status_updated_at=status_updated_at,
                pending_interaction=pending_interaction,
                pending_auth_method_selection=pending_auth_method_selection,
                pending_auth=pending_auth,
                interaction_history=interaction_history,
                orchestrator_events=orchestrator_events,
                effective_session_timeout_sec=effective_session_timeout_sec,
                completion=completion_payload,
                rebuild_mode=rebuild_mode,
            )
            fcmp_rows = [model.model_dump(mode="json") for model in fcmp_models]
            for row in fcmp_rows:
                validate_fcmp_event(row)
        metrics_payload = compute_protocol_metrics(rasp_models)

        write_jsonl(paths["events"], rasp_rows)
        write_jsonl(
            paths["diagnostics"],
            [
                row
                for row in rasp_rows
                if isinstance(row.get("event"), dict)
                and row["event"].get("category") == "diagnostic"
            ],
        )
        if force_rebuild or not existing_fcmp_rows:
            write_jsonl(paths["fcmp"], fcmp_rows)
        self.reindex_fcmp_global_seq(run_dir)
        paths["metrics"].parent.mkdir(parents=True, exist_ok=True)
        paths["metrics"].write_text(
            json.dumps(metrics_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "rasp_events": rasp_rows,
            "fcmp_events": fcmp_rows,
            "source_mode": source_mode,
            "fallback_used": fallback_used,
            "rebuild_diagnostics": rebuild_diagnostics,
            "mode": rebuild_mode,
        }

    def _read_attempt_meta(self, audit_dir: Path, attempt_number: int) -> Dict[str, Any]:
        meta_path = audit_dir / f"meta.{attempt_number}.json"
        if not meta_path.exists() or not meta_path.is_file():
            return {}
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    async def _resolve_attempt_pending_interaction(
        self,
        *,
        request_id: Optional[str],
        attempt_number: int,
        attempt_status: str,
        interaction_history: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        for item in interaction_history:
            if not isinstance(item, dict):
                continue
            if item.get("event_type") != "ask_user":
                continue
            source_attempt_obj = item.get("source_attempt")
            source_attempt: Optional[int]
            if isinstance(source_attempt_obj, int):
                source_attempt = source_attempt_obj
            else:
                interaction_id_obj = item.get("interaction_id")
                source_attempt = interaction_id_obj if isinstance(interaction_id_obj, int) else None
            if source_attempt != attempt_number:
                continue
            payload_obj = item.get("payload")
            if isinstance(payload_obj, dict):
                return payload_obj
        if request_id and attempt_status == "waiting_user":
            pending_obj = await maybe_await(self._run_store().get_pending_interaction(request_id))
            if isinstance(pending_obj, dict):
                source_attempt_obj = pending_obj.get("source_attempt")
                if isinstance(source_attempt_obj, int) and source_attempt_obj == attempt_number:
                    return pending_obj
        return None

    async def _resolve_attempt_pending_auth(
        self,
        *,
        request_id: Optional[str],
        attempt_status: str,
    ) -> Optional[Dict[str, Any]]:
        if request_id and attempt_status == "waiting_auth":
            pending_obj = await maybe_await(self._run_store().get_pending_auth(request_id))
            if isinstance(pending_obj, dict):
                return pending_obj
        return None

    async def _resolve_attempt_pending_auth_method_selection(
        self,
        *,
        request_id: Optional[str],
        attempt_status: str,
    ) -> Optional[Dict[str, Any]]:
        if request_id and attempt_status == "waiting_auth":
            pending_obj = await maybe_await(self._run_store().get_pending_auth_method_selection(request_id))
            if isinstance(pending_obj, dict):
                return pending_obj
        return None

    def _filter_events(
        self,
        *,
        rows: List[Dict[str, Any]],
        from_seq: Optional[int],
        to_seq: Optional[int],
        from_ts: Optional[str],
        to_ts: Optional[str],
    ) -> List[Dict[str, Any]]:
        from_seq_value = int(from_seq) if from_seq is not None else None
        to_seq_value = int(to_seq) if to_seq is not None else None
        from_ts_value = self._parse_optional_ts(from_ts)
        to_ts_value = self._parse_optional_ts(to_ts)

        filtered: List[Dict[str, Any]] = []
        for row in rows:
            seq_obj = row.get("seq")
            if not isinstance(seq_obj, int):
                continue
            if from_seq_value is not None and seq_obj < from_seq_value:
                continue
            if to_seq_value is not None and seq_obj > to_seq_value:
                continue
            ts_obj = self._parse_optional_ts(row.get("ts"))
            if from_ts_value is not None and ts_obj is not None and ts_obj < from_ts_value:
                continue
            if to_ts_value is not None and ts_obj is not None and ts_obj > to_ts_value:
                continue
            filtered.append(row)
        return filtered

    def _filter_valid_fcmp_rows(self, *, rows: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            try:
                validate_fcmp_event(row)
            except ProtocolSchemaViolation as exc:
                logger.warning("Skip invalid FCMP row (%s): %s", context, str(exc))
                continue
            filtered.append(row)
        return filtered

    def _filter_valid_rasp_rows(self, *, rows: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            try:
                validate_rasp_event(row)
            except ProtocolSchemaViolation as exc:
                logger.warning("Skip invalid RASP row (%s): %s", context, str(exc))
                continue
            filtered.append(row)
        return filtered

    def _filter_valid_chat_rows(self, *, rows: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            try:
                validate_chat_replay_event(row)
            except ProtocolSchemaViolation as exc:
                logger.warning("Skip invalid chat replay row (%s): %s", context, str(exc))
                continue
            filtered.append(row)
        return filtered

    def _filter_valid_orchestrator_rows(
        self,
        *,
        rows: List[Dict[str, Any]],
        context: str,
    ) -> List[Dict[str, Any]]:
        rows = self._backfill_orchestrator_seq(rows)
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            try:
                validate_orchestrator_event(row)
            except ProtocolSchemaViolation as exc:
                logger.warning("Skip invalid orchestrator row (%s): %s", context, str(exc))
                continue
            filtered.append(row)
        return filtered

    def _parse_optional_ts(self, value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    async def list_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = await maybe_await(self._run_store().list_requests_with_runs(limit=limit))
        return await self._build_run_rows(rows)

    async def list_runs_paginated(self, *, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        safe_page = max(1, int(page))
        safe_page_size = max(1, min(int(page_size), 1000))
        total = await maybe_await(self._run_store().count_requests_with_runs())
        rows = await maybe_await(
            self._run_store().list_requests_with_runs_page(
                page=safe_page,
                page_size=safe_page_size,
            )
        )
        runs = await self._build_run_rows(rows)
        total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 0
        return {
            "runs": runs,
            "page": safe_page,
            "page_size": safe_page_size,
            "total": total,
            "total_pages": total_pages,
        }

    async def _build_run_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for row in rows:
            run_id_obj = row.get("run_id")
            if not isinstance(run_id_obj, str) or not run_id_obj:
                continue
            run_id = run_id_obj
            run_dir = self._workspace().get_run_dir(run_id)
            status_payload = self._read_status_payload(run_dir) if run_dir else {}
            run_status = self._normalize_run_status(row, status_payload)
            file_state = self._build_file_state(run_dir)
            request_id_obj = row.get("request_id")
            request_id = request_id_obj if isinstance(request_id_obj, str) else ""
            await self._reconcile_waiting_auth_if_needed(request_id, run_status)
            await self._redrive_queued_resume_if_needed(request_id, run_status)
            if request_id:
                refreshed_row = await maybe_await(self._run_store().get_request_with_run(request_id))
                if isinstance(refreshed_row, dict):
                    row = refreshed_row
                run_dir = self._workspace().get_run_dir(run_id)
                status_payload = self._read_status_payload(run_dir) if run_dir else {}
                run_status = self._normalize_run_status(row, status_payload)
                file_state = self._build_file_state(run_dir or (Path(config.SYSTEM.RUNS_DIR) / run_id))
            updated_at = status_payload.get("updated_at")
            if not isinstance(updated_at, str):
                updated_at = self._derive_updated_at(run_dir, row)
            results.append(
                {
                    "request_id": request_id_obj,
                    "run_id": run_id,
                    "skill_id": row.get("skill_id"),
                    "engine": row.get("engine"),
                    "model": self._resolve_model_from_row(row),
                    "status": run_status,
                    "updated_at": updated_at,
                    "effective_session_timeout_sec": (
                        await maybe_await(self._run_store().get_effective_session_timeout(request_id))
                        if request_id
                        else None
                    ),
                    "recovery_state": row.get("recovery_state") or "none",
                    "recovered_at": row.get("recovered_at"),
                    "recovery_reason": row.get("recovery_reason"),
                    "file_state": file_state,
                }
            )
        return results

    async def get_run_detail(self, request_id: str) -> Dict[str, Any]:
        record = await maybe_await(self._run_store().get_request_with_run(request_id))
        if not record:
            raise ValueError("Request not found")
        run_id_obj = record.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise ValueError("Run not found")
        run_dir = self._workspace().get_run_dir(run_id_obj)
        run_dir_path = run_dir or (Path(config.SYSTEM.RUNS_DIR) / run_id_obj)
        status_payload = self._read_status_payload(run_dir_path) if run_dir_path.exists() else {}
        run_status = self._normalize_run_status(record, status_payload)
        await self._reconcile_waiting_auth_if_needed(request_id, run_status)
        await self._redrive_queued_resume_if_needed(request_id, run_status)
        refreshed_record = await maybe_await(self._run_store().get_request_with_run(request_id))
        if isinstance(refreshed_record, dict):
            record = refreshed_record
        run_dir = self._workspace().get_run_dir(run_id_obj)
        run_dir_path = run_dir or (Path(config.SYSTEM.RUNS_DIR) / run_id_obj)
        status_payload = self._read_status_payload(run_dir_path) if run_dir_path.exists() else {}
        run_status = self._normalize_run_status(record, status_payload)
        file_state = self._build_file_state(run_dir_path)
        entries = self._list_run_entries(run_dir_path) if run_dir_path.exists() else []
        runtime_options = record.get("runtime_options", {})
        effective_runtime_options = record.get("effective_runtime_options", runtime_options)
        requested_execution_mode = None
        effective_execution_mode = None
        conversation_mode = _resolve_conversation_mode(record.get("client_metadata"))
        interactive_auto_reply: bool | None = None
        interactive_reply_timeout_sec: int | None = None
        if isinstance(runtime_options, dict):
            requested_execution_mode = runtime_options.get("execution_mode")
        if isinstance(effective_runtime_options, dict):
            effective_execution_mode = effective_runtime_options.get("execution_mode")
            auto_reply_obj = effective_runtime_options.get("interactive_auto_reply")
            if isinstance(auto_reply_obj, bool):
                interactive_auto_reply = auto_reply_obj
            timeout_obj = effective_runtime_options.get("interactive_reply_timeout_sec")
            if isinstance(timeout_obj, int) and timeout_obj >= 0:
                interactive_reply_timeout_sec = timeout_obj

        return {
            "request_id": request_id,
            "run_id": run_id_obj,
            "run_dir": str(run_dir_path),
            "skill_id": record.get("skill_id"),
            "engine": record.get("engine"),
            "model": self._resolve_model_from_row(record),
            "status": run_status,
            "updated_at": status_payload.get("updated_at") or self._derive_updated_at(run_dir_path, record),
            "effective_session_timeout_sec": await maybe_await(self._run_store().get_effective_session_timeout(request_id)),
            "recovery_state": record.get("recovery_state") or "none",
            "recovered_at": record.get("recovered_at"),
            "recovery_reason": record.get("recovery_reason"),
            "entries": entries,
            "file_state": file_state,
            "poll_logs": run_status in RUNNING_STATUSES,
            "requested_execution_mode": requested_execution_mode,
            "effective_execution_mode": effective_execution_mode,
            "conversation_mode": conversation_mode,
            "interactive_auto_reply": interactive_auto_reply,
            "interactive_reply_timeout_sec": interactive_reply_timeout_sec,
            "effective_interactive_require_user_reply": bool(
                effective_execution_mode == "interactive" and conversation_mode == "session"
            ),
            "effective_interactive_reply_timeout_sec": interactive_reply_timeout_sec,
            "current_attempt": status_payload.get("current_attempt"),
            "pending_owner": status_payload.get("pending_owner"),
            "resume_ticket_id": status_payload.get("resume_ticket_id"),
            "resume_cause": status_payload.get("resume_cause"),
            "source_attempt": status_payload.get("source_attempt"),
            "target_attempt": status_payload.get("target_attempt"),
        }

    def _resolve_model_from_row(self, row: Dict[str, Any]) -> str | None:
        if not isinstance(row, dict):
            return None
        engine_options = row.get("engine_options")
        if not isinstance(engine_options, dict):
            engine_options_raw = row.get("engine_options_json")
            if isinstance(engine_options_raw, str) and engine_options_raw:
                try:
                    parsed = json.loads(engine_options_raw)
                except (json.JSONDecodeError, TypeError, ValueError):
                    parsed = {}
                engine_options = parsed if isinstance(parsed, dict) else {}
            else:
                engine_options = {}
        for key in ("model", "model_id"):
            value = engine_options.get(key) if isinstance(engine_options, dict) else None
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    async def resolve_run_file_path(self, request_id: str, relative_path: str) -> Path:
        detail = await self.get_run_detail(request_id)
        run_dir = Path(detail["run_dir"])
        normalized = normalize_relative_path(relative_path)
        if not run_file_filter_service.path_allowed_for_run_explorer(normalized):
            raise ValueError("path is filtered")
        requested = PurePosixPath(normalized)
        candidate = (run_dir / requested).resolve(strict=False)
        root_resolved = run_dir.resolve(strict=True)
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError("path escapes run root") from exc
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError("file not found")
        candidate_resolved = candidate.resolve(strict=True)
        try:
            candidate_resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError("path escapes run root") from exc
        return candidate_resolved

    async def build_run_file_preview(self, request_id: str, relative_path: str) -> Dict[str, Any]:
        file_path = await self.resolve_run_file_path(request_id, relative_path)
        return build_preview_payload(file_path)

    async def get_logs_tail(self, request_id: str, max_bytes: int = 64 * 1024) -> Dict[str, Any]:
        detail = await self.get_run_detail(request_id)
        run_dir = Path(detail["run_dir"])
        latest_attempt = max(1, self._latest_attempt_number(run_dir))
        audit_dir = run_dir / AUDIT_DIR_NAME
        attempted_stdout = audit_dir / f"stdout.{latest_attempt}.log"
        attempted_stderr = audit_dir / f"stderr.{latest_attempt}.log"
        stdout_path = attempted_stdout
        stderr_path = attempted_stderr
        return {
            "request_id": request_id,
            "run_id": detail["run_id"],
            "status": detail["status"],
            "poll": detail["status"] in RUNNING_STATUSES,
            "stdout": self._tail_file(stdout_path, max_bytes=max_bytes),
            "stderr": self._tail_file(stderr_path, max_bytes=max_bytes),
        }

    def _read_status_payload(self, run_dir: Path) -> Dict[str, Any]:
        state_file = run_dir / ".state" / "state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    return payload
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
        return {}

    def _normalize_run_status(self, record: Dict[str, Any], status_payload: Dict[str, Any]) -> str:
        status_obj = status_payload.get("status")
        if isinstance(status_obj, str) and status_obj:
            return status_obj
        run_status_obj = record.get("run_status")
        if isinstance(run_status_obj, str) and run_status_obj:
            return run_status_obj
        return "queued"

    def _build_file_state(self, run_dir: Path | None) -> Dict[str, Dict[str, Any]]:
        if not run_dir:
            return {}
        latest_attempt = max(1, self._latest_attempt_number(run_dir))
        audit_dir = run_dir / AUDIT_DIR_NAME
        targets = {
            "state": run_dir / ".state" / "state.json",
            "dispatch": run_dir / ".state" / "dispatch.json",
            "request_input": run_dir / ".audit" / "request_input.json",
            "stdout": audit_dir / f"stdout.{latest_attempt}.log",
            "stderr": audit_dir / f"stderr.{latest_attempt}.log",
            "result": run_dir / "result" / "result.json",
            "artifacts_dir": run_dir / "artifacts",
        }
        state: Dict[str, Dict[str, Any]] = {}
        for name, path in targets.items():
            exists = path.exists()
            item: Dict[str, Any] = {"exists": exists}
            if exists:
                stat = path.stat()
                item["size"] = stat.st_size
                item["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                item["is_dir"] = path.is_dir()
            state[name] = item
        return state

    def _list_run_entries(self, run_dir: Path) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def _walk(current: Path, depth: int) -> None:
            children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for child in children:
                rel = child.relative_to(run_dir).as_posix()
                is_dir = child.is_dir() and not child.is_symlink()
                if not run_file_filter_service.include_in_run_explorer(rel, is_dir=is_dir):
                    continue
                entries.append(
                    {
                        "rel_path": rel,
                        "name": child.name,
                        "is_dir": is_dir,
                        "depth": depth,
                    }
                )
                if is_dir:
                    _walk(child, depth + 1)

        _walk(run_dir, 0)
        return entries

    def _derive_updated_at(self, run_dir: Path | None, record: Dict[str, Any]) -> str | None:
        if run_dir and run_dir.exists():
            try:
                mtime = run_dir.stat().st_mtime
                return datetime.fromtimestamp(mtime).isoformat()
            except OSError:
                pass
        request_created = record.get("request_created_at")
        return request_created if isinstance(request_created, str) else None

    def _tail_file(self, path: Path, max_bytes: int) -> str:
        if not path.exists() or not path.is_file():
            return ""
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read_size = min(size, max_bytes)
            if read_size <= 0:
                return ""
            f.seek(size - read_size)
            data = f.read(read_size)
        return data.decode("utf-8", errors="replace")

    async def _read_pending_interaction_id(self, request_id: Optional[str]) -> Optional[int]:
        if not request_id:
            return None
        pending = await maybe_await(self._run_store().get_pending_interaction(request_id))
        if not isinstance(pending, dict):
            return None
        value = pending.get("interaction_id")
        if value is None:
            return None
        try:
            interaction_id = int(value)
        except (TypeError, ValueError):
            return None
        if interaction_id <= 0:
            return None
        return interaction_id

    async def _read_pending_auth_session_id(self, request_id: Optional[str]) -> Optional[str]:
        if not request_id:
            return None
        pending = await maybe_await(self._run_store().get_pending_auth(request_id))
        if not isinstance(pending, dict):
            return None
        value = pending.get("auth_session_id")
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None


run_observability_service = RunObservabilityService()
logger = logging.getLogger(__name__)
