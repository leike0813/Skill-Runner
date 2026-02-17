import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from .run_store import run_store
from .workspace_manager import workspace_manager
from .skill_browser import (
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)


RUNNING_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


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

    async def iter_sse_events(
        self,
        *,
        run_dir: Path,
        request_id: Optional[str],
        stdout_from: int = 0,
        stderr_from: int = 0,
        chunk_bytes: int = 8 * 1024,
        heartbeat_interval_sec: float = 5.0,
        poll_interval_sec: float = 0.2,
        is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        logs_dir = run_dir / "logs"
        stdout_path = logs_dir / "stdout.txt"
        stderr_path = logs_dir / "stderr.txt"
        stdout_offset = max(0, int(stdout_from))
        stderr_offset = max(0, int(stderr_from))

        status_payload = self._read_status_payload(run_dir)
        status = status_payload.get("status")
        if not isinstance(status, str) or not status:
            status = "queued"
        snapshot = {
            "status": status,
            "stdout_offset": stdout_offset,
            "stderr_offset": stderr_offset,
        }
        pending_id = self._read_pending_interaction_id(request_id)
        if pending_id is not None:
            snapshot["pending_interaction_id"] = pending_id
        yield {"event": "snapshot", "data": snapshot}

        last_status = status
        last_updated_at = status_payload.get("updated_at")
        last_heartbeat_at = time.monotonic()

        while True:
            if is_disconnected is not None and await is_disconnected():
                yield {"event": "end", "data": {"reason": "client_closed"}}
                return

            emitted = False
            stdout_evt = self.read_log_increment(stdout_path, stdout_offset, chunk_bytes)
            if stdout_evt["to"] > stdout_offset:
                stdout_offset = int(stdout_evt["to"])
                yield {"event": "stdout", "data": stdout_evt}
                emitted = True

            stderr_evt = self.read_log_increment(stderr_path, stderr_offset, chunk_bytes)
            if stderr_evt["to"] > stderr_offset:
                stderr_offset = int(stderr_evt["to"])
                yield {"event": "stderr", "data": stderr_evt}
                emitted = True

            status_payload = self._read_status_payload(run_dir)
            status_obj = status_payload.get("status")
            current_status = status_obj if isinstance(status_obj, str) and status_obj else last_status
            updated_at_obj = status_payload.get("updated_at")
            updated_at = updated_at_obj if isinstance(updated_at_obj, str) else None
            error_payload = status_payload.get("error")
            error_code = error_payload.get("code") if isinstance(error_payload, dict) else None
            pending_id = self._read_pending_interaction_id(request_id)

            should_emit_status = current_status != last_status
            if should_emit_status:
                status_event: Dict[str, Any] = {"status": current_status}
                if updated_at:
                    status_event["updated_at"] = updated_at
                if isinstance(error_code, str) and error_code:
                    status_event["error_code"] = error_code
                if pending_id is not None:
                    status_event["pending_interaction_id"] = pending_id
                yield {"event": "status", "data": status_event}
                emitted = True
                last_status = current_status
                last_updated_at = updated_at

            if current_status == "waiting_user":
                if not should_emit_status:
                    status_event = {"status": current_status}
                    if updated_at:
                        status_event["updated_at"] = updated_at
                    if isinstance(error_code, str) and error_code:
                        status_event["error_code"] = error_code
                    if pending_id is not None:
                        status_event["pending_interaction_id"] = pending_id
                    yield {"event": "status", "data": status_event}
                yield {"event": "end", "data": {"reason": "waiting_user"}}
                return
            if current_status in TERMINAL_STATUSES:
                if not should_emit_status:
                    status_event = {"status": current_status}
                    if updated_at:
                        status_event["updated_at"] = updated_at
                    if isinstance(error_code, str) and error_code:
                        status_event["error_code"] = error_code
                    yield {"event": "status", "data": status_event}
                yield {"event": "end", "data": {"reason": "terminal"}}
                return

            now = time.monotonic()
            if not emitted and now - last_heartbeat_at >= heartbeat_interval_sec:
                yield {"event": "heartbeat", "data": {"ts": datetime.utcnow().isoformat()}}
                last_heartbeat_at = now
            elif emitted:
                last_heartbeat_at = now
                if updated_at:
                    last_updated_at = updated_at
            else:
                if updated_at and updated_at != last_updated_at:
                    last_updated_at = updated_at
            await asyncio.sleep(poll_interval_sec)

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
