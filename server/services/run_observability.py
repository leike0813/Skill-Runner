import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from .run_store import run_store
from .runtime_event_protocol import (
    build_fcmp_events,
    build_rasp_events,
    compute_protocol_metrics,
    read_jsonl,
    write_jsonl,
)
from .protocol_schema_registry import (
    ProtocolSchemaViolation,
    validate_fcmp_event,
    validate_orchestrator_event,
    validate_rasp_event,
)
from .workspace_manager import workspace_manager
from .skill_browser import (
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)


RUNNING_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
AUDIT_DIR_NAME = ".audit"
RASP_EVENTS_FILE_PREFIX = "events"
PARSER_DIAGNOSTICS_FILE_PREFIX = "parser_diagnostics"
FCMP_EVENTS_FILE_PREFIX = "fcmp_events"
PROTOCOL_METRICS_FILE_PREFIX = "protocol_metrics"
ORCHESTRATOR_EVENTS_FILE_PREFIX = "orchestrator_events"
ATTEMPT_FILE_PATTERNS = (
    re.compile(r"^meta\.(\d+)\.json$"),
    re.compile(r"^events\.(\d+)\.jsonl$"),
    re.compile(r"^fcmp_events\.(\d+)\.jsonl$"),
    re.compile(r"^orchestrator_events\.(\d+)\.jsonl$"),
    re.compile(r"^stdout\.(\d+)\.log$"),
    re.compile(r"^stderr\.(\d+)\.log$"),
    re.compile(r"^pty-output\.(\d+)\.log$"),
)


class RunObservabilityService:
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

    def read_log_range(
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
        attempt_number = self._resolve_attempt_number(
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
        snapshot = {
            "status": status,
            "cursor": max(0, int(cursor)),
        }
        pending_id = self._read_pending_interaction_id(request_id)
        if pending_id is not None:
            snapshot["pending_interaction_id"] = pending_id
        yield {"event": "snapshot", "data": snapshot}

        last_heartbeat_at = time.monotonic()
        last_chat_event_seq = max(0, int(cursor))
        bootstrap_events = self.list_event_history(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=last_chat_event_seq + 1,
            to_seq=None,
            from_ts=None,
            to_ts=None,
        )
        for event in bootstrap_events:
            seq_obj = event.get("seq")
            if not isinstance(seq_obj, int) or seq_obj <= last_chat_event_seq:
                continue
            yield {"event": "chat_event", "data": event}
            last_chat_event_seq = seq_obj

        while True:
            if is_disconnected is not None and await is_disconnected():
                return

            emitted = False

            status_payload = self._read_status_payload(run_dir)
            status_obj = status_payload.get("status")
            current_status = status_obj if isinstance(status_obj, str) and status_obj else status

            protocol_payload = self.list_event_history(
                run_dir=run_dir,
                request_id=request_id,
                from_seq=last_chat_event_seq + 1,
                to_seq=None,
                from_ts=None,
                to_ts=None,
            )
            for event in protocol_payload:
                seq_obj = event.get("seq")
                if not isinstance(seq_obj, int) or seq_obj <= last_chat_event_seq:
                    continue
                yield {"event": "chat_event", "data": event}
                emitted = True
                last_chat_event_seq = seq_obj

            if current_status == "waiting_user":
                return
            if current_status in TERMINAL_STATUSES:
                return

            now = time.monotonic()
            if not emitted and now - last_heartbeat_at >= heartbeat_interval_sec:
                yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}
                last_heartbeat_at = now
            elif emitted:
                last_heartbeat_at = now
            await asyncio.sleep(poll_interval_sec)

    def list_event_history(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        from_seq: Optional[int] = None,
        to_seq: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        attempts = self._list_available_attempts(run_dir)
        if not attempts:
            attempts = [1]
        rows: List[Dict[str, Any]] = []
        for attempt_number in attempts:
            payload = self.list_protocol_history(
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

    def list_protocol_history(
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
    ) -> Dict[str, Any]:
        normalized_stream = stream.strip().lower()
        if normalized_stream not in {"fcmp", "rasp", "orchestrator"}:
            raise ValueError("stream must be one of: fcmp, rasp, orchestrator")

        status_payload = self._read_status_payload(run_dir)
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        runtime_attempt = self._resolve_attempt_number(
            request_id=request_id,
            status=status,
            run_dir=run_dir,
            requested_attempt=None,
        )
        selected_attempt = self._resolve_attempt_number(
            request_id=request_id,
            status=status,
            run_dir=run_dir,
            requested_attempt=attempt,
        )
        paths = self._protocol_paths(run_dir, selected_attempt)
        should_materialize = normalized_stream in {"fcmp", "rasp"}
        if not should_materialize:
            should_materialize = selected_attempt == runtime_attempt
        if not should_materialize:
            should_materialize = not (
                paths["events"].exists()
                and paths["fcmp"].exists()
                and paths["orchestrator"].exists()
            )
        if should_materialize:
            self._materialize_protocol_stream(
                run_dir=run_dir,
                request_id=request_id,
                status_payload=status_payload,
                attempt_number=selected_attempt,
            )
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
        return {
            "attempt": selected_attempt,
            "available_attempts": self._list_available_attempts(run_dir),
            "events": filtered,
        }

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
        }

    def _resolve_engine_name(self, request_id: Optional[str]) -> str:
        if not request_id:
            return "unknown"
        request_record = run_store.get_request(request_id)
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
                except Exception:
                    continue
                if value > 0:
                    attempts.add(value)
                break
        return sorted(attempts)

    def _resolve_attempt_number(
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
        request_record = run_store.get_request(request_id)
        if not request_record:
            return available_attempts[-1] if available_attempts else 1
        runtime_options = request_record.get("runtime_options")
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
        interaction_count = run_store.get_interaction_count(request_id)
        return max(1, int(interaction_count) + 1)

    def _materialize_protocol_stream(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        status_payload: Dict[str, Any],
        attempt_number: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        run_id = run_dir.name
        engine_name = self._resolve_engine_name(request_id)
        if attempt_number is None:
            attempt_number = self._resolve_attempt_number(
                request_id,
                status=status,
                run_dir=run_dir,
            )

        audit_dir = run_dir / AUDIT_DIR_NAME
        attempt_meta = self._read_attempt_meta(audit_dir, attempt_number)
        attempt_status_obj = attempt_meta.get("status")
        attempt_status = (
            attempt_status_obj
            if isinstance(attempt_status_obj, str) and attempt_status_obj
            else status
        )

        attempted_stdout = audit_dir / f"stdout.{attempt_number}.log"
        attempted_stderr = audit_dir / f"stderr.{attempt_number}.log"
        attempted_pty = audit_dir / f"pty-output.{attempt_number}.log"
        stdout_path = attempted_stdout
        stderr_path = attempted_stderr
        pty_path = attempted_pty if attempted_pty.exists() else None

        # Strict audit-only mode: never fallback to legacy run_dir/logs.
        if not stdout_path.exists() and not stderr_path.exists() and pty_path is None:
            warning_payload = {
                "ts": datetime.utcnow().isoformat(),
                "event": {"category": "diagnostic", "type": "diagnostic.warning"},
                "data": {
                    "code": "ATTEMPT_AUDIT_LOG_MISSING",
                    "attempt_number": attempt_number,
                },
            }
            paths = self._protocol_paths(run_dir, attempt_number)
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
            return {"rasp_events": [], "fcmp_events": []}
        completion_obj = attempt_meta.get("completion")
        completion_payload: Optional[Dict[str, Any]] = (
            completion_obj if isinstance(completion_obj, dict) else None
        )
        interaction_history = (
            run_store.list_interaction_history(request_id)
            if request_id
            else []
        )
        pending_interaction = self._resolve_attempt_pending_interaction(
            request_id=request_id,
            attempt_number=attempt_number,
            attempt_status=attempt_status,
            interaction_history=interaction_history,
        )
        orchestrator_events = self._filter_valid_orchestrator_rows(
            rows=read_jsonl(self._protocol_paths(run_dir, attempt_number)["orchestrator"]),
            context=f"materialize:{request_id or run_id}",
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
            run_store.get_effective_session_timeout(request_id)
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
            completion=completion_payload,
        )
        rasp_rows = [model.model_dump(mode="json") for model in rasp_models]
        for row in rasp_rows:
            validate_rasp_event(row)
        fcmp_models = build_fcmp_events(
            rasp_models,
            status=attempt_status,
            status_updated_at=status_updated_at,
            pending_interaction=pending_interaction,
            interaction_history=interaction_history,
            orchestrator_events=orchestrator_events,
            effective_session_timeout_sec=effective_session_timeout_sec,
            completion=completion_payload,
        )
        fcmp_rows = [model.model_dump(mode="json") for model in fcmp_models]
        for row in fcmp_rows:
            validate_fcmp_event(row)
        metrics_payload = compute_protocol_metrics(rasp_models)

        paths = self._protocol_paths(run_dir, attempt_number)
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
        write_jsonl(paths["fcmp"], fcmp_rows)
        self.reindex_fcmp_global_seq(run_dir)
        paths["metrics"].parent.mkdir(parents=True, exist_ok=True)
        paths["metrics"].write_text(
            json.dumps(metrics_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"rasp_events": rasp_rows, "fcmp_events": fcmp_rows}

    def _read_attempt_meta(self, audit_dir: Path, attempt_number: int) -> Dict[str, Any]:
        meta_path = audit_dir / f"meta.{attempt_number}.json"
        if not meta_path.exists() or not meta_path.is_file():
            return {}
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _resolve_attempt_pending_interaction(
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
            interaction_id_obj = item.get("interaction_id")
            if not isinstance(interaction_id_obj, int) or interaction_id_obj != attempt_number:
                continue
            payload_obj = item.get("payload")
            if isinstance(payload_obj, dict):
                return payload_obj
        if request_id and attempt_status == "waiting_user":
            pending_obj = run_store.get_pending_interaction(request_id)
            if isinstance(pending_obj, dict):
                interaction_id_obj = pending_obj.get("interaction_id")
                if isinstance(interaction_id_obj, int) and interaction_id_obj == attempt_number:
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

    def list_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = run_store.list_requests_with_runs(limit=limit)
        results: List[Dict[str, Any]] = []
        for row in rows:
            run_id_obj = row.get("run_id")
            if not isinstance(run_id_obj, str) or not run_id_obj:
                continue
            run_id = run_id_obj
            run_dir = workspace_manager.get_run_dir(run_id)
            status_payload = self._read_status_payload(run_dir) if run_dir else {}
            run_status = self._normalize_run_status(row, status_payload)
            file_state = self._build_file_state(run_dir)
            request_id_obj = row.get("request_id")
            request_id = request_id_obj if isinstance(request_id_obj, str) else ""
            updated_at = status_payload.get("updated_at")
            if not isinstance(updated_at, str):
                updated_at = self._derive_updated_at(run_dir, row)
            results.append(
                {
                    "request_id": request_id_obj,
                    "run_id": run_id,
                    "skill_id": row.get("skill_id"),
                    "engine": row.get("engine"),
                    "status": run_status,
                    "updated_at": updated_at,
                    "effective_session_timeout_sec": (
                        run_store.get_effective_session_timeout(request_id) if request_id else None
                    ),
                    "recovery_state": row.get("recovery_state") or "none",
                    "recovered_at": row.get("recovered_at"),
                    "recovery_reason": row.get("recovery_reason"),
                    "file_state": file_state,
                }
            )
        return results

    def get_run_detail(self, request_id: str) -> Dict[str, Any]:
        record = run_store.get_request_with_run(request_id)
        if not record:
            raise ValueError("Request not found")
        run_id_obj = record.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise ValueError("Run not found")
        run_dir = workspace_manager.get_run_dir(run_id_obj)
        if not run_dir or not run_dir.exists():
            raise FileNotFoundError("Run directory not found")

        status_payload = self._read_status_payload(run_dir)
        run_status = self._normalize_run_status(record, status_payload)
        file_state = self._build_file_state(run_dir)
        entries = list_skill_entries(run_dir)

        return {
            "request_id": request_id,
            "run_id": run_id_obj,
            "run_dir": str(run_dir),
            "skill_id": record.get("skill_id"),
            "engine": record.get("engine"),
            "status": run_status,
            "updated_at": status_payload.get("updated_at") or self._derive_updated_at(run_dir, record),
            "effective_session_timeout_sec": run_store.get_effective_session_timeout(request_id),
            "recovery_state": record.get("recovery_state") or "none",
            "recovered_at": record.get("recovered_at"),
            "recovery_reason": record.get("recovery_reason"),
            "entries": entries,
            "file_state": file_state,
            "poll_logs": run_status in RUNNING_STATUSES,
        }

    def resolve_run_file_path(self, request_id: str, relative_path: str) -> Path:
        detail = self.get_run_detail(request_id)
        run_dir = Path(detail["run_dir"])
        return resolve_skill_file_path(run_dir, relative_path)

    def build_run_file_preview(self, request_id: str, relative_path: str) -> Dict[str, Any]:
        file_path = self.resolve_run_file_path(request_id, relative_path)
        return build_preview_payload(file_path)

    def get_logs_tail(self, request_id: str, max_bytes: int = 64 * 1024) -> Dict[str, Any]:
        detail = self.get_run_detail(request_id)
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
        status_file = run_dir / "status.json"
        if not status_file.exists():
            return {}
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
            return {}
        except Exception:
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
            "status": run_dir / "status.json",
            "input": run_dir / "input.json",
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

    def _derive_updated_at(self, run_dir: Path | None, record: Dict[str, Any]) -> str | None:
        if run_dir and run_dir.exists():
            try:
                mtime = run_dir.stat().st_mtime
                return datetime.fromtimestamp(mtime).isoformat()
            except Exception:
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

    def _read_pending_interaction_id(self, request_id: Optional[str]) -> Optional[int]:
        if not request_id:
            return None
        pending = run_store.get_pending_interaction(request_id)
        if not isinstance(pending, dict):
            return None
        value = pending.get("interaction_id")
        if value is None:
            return None
        try:
            interaction_id = int(value)
        except Exception:
            return None
        if interaction_id <= 0:
            return None
        return interaction_id


run_observability_service = RunObservabilityService()
logger = logging.getLogger(__name__)
