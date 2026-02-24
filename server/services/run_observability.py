import asyncio
import json
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
from .workspace_manager import workspace_manager
from .skill_browser import (
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)


RUNNING_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
AUDIT_DIR_NAME = ".audit"
RASP_EVENTS_FILE = "events.jsonl"
PARSER_DIAGNOSTICS_FILE = "parser_diagnostics.jsonl"
FCMP_EVENTS_FILE = "fcmp_events.jsonl"
PROTOCOL_METRICS_FILE = "protocol_metrics.json"
ORCHESTRATOR_EVENTS_FILE = "orchestrator_events.jsonl"


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
        )
        logs_dir = run_dir / "logs"
        audit_dir = run_dir / AUDIT_DIR_NAME
        if safe_stream == "pty":
            attempted_path = audit_dir / f"pty-output.{attempt_number}.log"
            path = attempted_path if attempted_path.exists() else logs_dir / "pty-output.txt"
        else:
            attempted_path = audit_dir / f"{safe_stream}.{attempt_number}.log"
            path = attempted_path if attempted_path.exists() else logs_dir / f"{safe_stream}.txt"
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

        protocol_payload = self._materialize_protocol_stream(
            run_dir=run_dir,
            request_id=request_id,
            status_payload=status_payload,
        )
        for event in protocol_payload["fcmp_events"]:
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

            protocol_payload = self._materialize_protocol_stream(
                run_dir=run_dir,
                request_id=request_id,
                status_payload=status_payload,
            )
            for event in protocol_payload["fcmp_events"]:
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
        status_payload = self._read_status_payload(run_dir)
        self._materialize_protocol_stream(
            run_dir=run_dir,
            request_id=request_id,
            status_payload=status_payload,
        )
        paths = self._protocol_paths(run_dir)
        rows = read_jsonl(paths["fcmp"])
        return self._filter_events(
            rows=rows,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )

    def _protocol_paths(self, run_dir: Path) -> Dict[str, Path]:
        audit_dir = run_dir / AUDIT_DIR_NAME
        return {
            "audit_dir": audit_dir,
            "events": audit_dir / RASP_EVENTS_FILE,
            "diagnostics": audit_dir / PARSER_DIAGNOSTICS_FILE,
            "fcmp": audit_dir / FCMP_EVENTS_FILE,
            "metrics": audit_dir / PROTOCOL_METRICS_FILE,
            "orchestrator": audit_dir / ORCHESTRATOR_EVENTS_FILE,
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
        audit_dir = run_dir / AUDIT_DIR_NAME
        if not audit_dir.exists() or not audit_dir.is_dir():
            return 0
        latest = 0
        for path in audit_dir.glob("meta.*.json"):
            parts = path.name.split(".")
            if len(parts) != 3:
                continue
            try:
                candidate = int(parts[1])
            except Exception:
                continue
            if candidate > latest:
                latest = candidate
        return latest

    def _resolve_attempt_number(
        self,
        request_id: Optional[str],
        *,
        status: str,
        run_dir: Path,
    ) -> int:
        if not request_id:
            return 1
        request_record = run_store.get_request(request_id)
        if not request_record:
            return 1
        runtime_options = request_record.get("runtime_options")
        execution_mode = ""
        if isinstance(runtime_options, dict):
            execution_mode_obj = runtime_options.get("execution_mode")
            if isinstance(execution_mode_obj, str):
                execution_mode = execution_mode_obj
        if execution_mode != "interactive":
            return 1
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
    ) -> Dict[str, List[Dict[str, Any]]]:
        logs_dir = run_dir / "logs"
        status_obj = status_payload.get("status")
        status = status_obj if isinstance(status_obj, str) and status_obj else "queued"
        pending_payload = run_store.get_pending_interaction(request_id) if request_id else None
        pending_interaction = pending_payload if isinstance(pending_payload, dict) else None
        run_id = run_dir.name
        engine_name = self._resolve_engine_name(request_id)
        attempt_number = self._resolve_attempt_number(
            request_id,
            status=status,
            run_dir=run_dir,
        )

        audit_dir = run_dir / AUDIT_DIR_NAME
        attempted_stdout_path = audit_dir / f"stdout.{attempt_number}.log"
        attempted_stderr_path = audit_dir / f"stderr.{attempt_number}.log"
        attempted_pty_path = audit_dir / f"pty-output.{attempt_number}.log"
        stdout_path = attempted_stdout_path if attempted_stdout_path.exists() else logs_dir / "stdout.txt"
        stderr_path = attempted_stderr_path if attempted_stderr_path.exists() else logs_dir / "stderr.txt"
        pty_path = attempted_pty_path if attempted_pty_path.exists() else logs_dir / "pty-output.txt"
        completion_payload: Optional[Dict[str, Any]] = None
        meta_path = audit_dir / f"meta.{attempt_number}.json"
        if meta_path.exists():
            try:
                meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
                completion_obj = meta_payload.get("completion")
                if isinstance(completion_obj, dict):
                    completion_payload = completion_obj
            except Exception:
                completion_payload = None
        interaction_history = (
            run_store.list_interaction_history(request_id)
            if request_id
            else []
        )
        orchestrator_events = read_jsonl(self._protocol_paths(run_dir)["orchestrator"])
        status_updated_at_obj = status_payload.get("updated_at")
        status_updated_at = status_updated_at_obj if isinstance(status_updated_at_obj, str) else None
        effective_session_timeout_sec = (
            run_store.get_effective_session_timeout(request_id)
            if request_id
            else None
        )

        rasp_models = build_rasp_events(
            run_id=run_id,
            engine=engine_name,
            attempt_number=attempt_number,
            status=status,
            pending_interaction=pending_interaction,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            pty_path=pty_path,
            completion=completion_payload,
        )
        rasp_rows = [model.model_dump(mode="json") for model in rasp_models]
        fcmp_models = build_fcmp_events(
            rasp_models,
            status=status,
            status_updated_at=status_updated_at,
            pending_interaction=pending_interaction,
            interaction_history=interaction_history,
            orchestrator_events=orchestrator_events,
            effective_session_timeout_sec=effective_session_timeout_sec,
            completion=completion_payload,
        )
        fcmp_rows = [model.model_dump(mode="json") for model in fcmp_models]
        metrics_payload = compute_protocol_metrics(rasp_models)

        paths = self._protocol_paths(run_dir)
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
        paths["metrics"].parent.mkdir(parents=True, exist_ok=True)
        paths["metrics"].write_text(
            json.dumps(metrics_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"rasp_events": rasp_rows, "fcmp_events": fcmp_rows}

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
        logs_dir = run_dir / "logs"
        stdout_path = logs_dir / "stdout.txt"
        stderr_path = logs_dir / "stderr.txt"
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
        targets = {
            "status": run_dir / "status.json",
            "input": run_dir / "input.json",
            "prompt": run_dir / "logs" / "prompt.txt",
            "stdout": run_dir / "logs" / "stdout.txt",
            "stderr": run_dir / "logs" / "stderr.txt",
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
