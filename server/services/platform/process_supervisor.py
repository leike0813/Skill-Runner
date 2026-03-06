from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Literal

from server.config import config
from server.services.platform.process_lease_store import ProcessLeaseStore, process_lease_store
from server.services.platform.process_termination import (
    PopenProcess,
    TerminationResult,
    terminate_asyncio_process_tree,
    terminate_pid_tree,
    terminate_popen_process_tree,
)

logger = logging.getLogger(__name__)

OwnerKind = Literal["run_attempt", "auth_session", "ui_shell"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _ActiveProcessRef:
    process_type: Literal["asyncio", "popen"]
    process: Any
    lease: dict[str, Any]


class RuntimeProcessSupervisor:
    def __init__(self, lease_store: ProcessLeaseStore | None = None) -> None:
        self._lease_store = lease_store or process_lease_store
        self._lock = RLock()
        self._active_by_lease_id: dict[str, _ActiveProcessRef] = {}
        self._startup_orphan_reports: list[dict[str, Any]] = []
        self._sweep_task: asyncio.Task[None] | None = None

    def _enabled(self) -> bool:
        return bool(config.SYSTEM.PROCESS_SUPERVISOR_ENABLED)

    def _new_lease_payload(
        self,
        *,
        lease_id: str,
        owner_kind: OwnerKind,
        owner_id: str,
        pid: int,
        request_id: str | None,
        run_id: str | None,
        attempt_number: int | None,
        engine: str | None,
        transport: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now_iso = _utc_now_iso()
        payload: dict[str, Any] = {
            "lease_id": lease_id,
            "owner_kind": owner_kind,
            "owner_id": owner_id,
            "pid": int(pid),
            "request_id": request_id,
            "run_id": run_id,
            "attempt_number": attempt_number,
            "engine": engine,
            "transport": transport,
            "created_at": now_iso,
            "updated_at": now_iso,
            "status": "active",
        }
        if metadata:
            payload["metadata"] = dict(metadata)
        return payload

    def register_asyncio_process(
        self,
        *,
        owner_kind: OwnerKind,
        owner_id: str,
        process: asyncio.subprocess.Process,
        request_id: str | None = None,
        run_id: str | None = None,
        attempt_number: int | None = None,
        engine: str | None = None,
        transport: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if not self._enabled():
            return None
        pid = int(process.pid or 0)
        if pid <= 0:
            logger.warning("Process supervisor skipped asyncio lease registration due to invalid pid")
            return None
        lease_id = str(uuid.uuid4())
        payload = self._new_lease_payload(
            lease_id=lease_id,
            owner_kind=owner_kind,
            owner_id=owner_id,
            pid=pid,
            request_id=request_id,
            run_id=run_id,
            attempt_number=attempt_number,
            engine=engine,
            transport=transport,
            metadata=metadata,
        )
        self._lease_store.upsert_active(payload)
        with self._lock:
            self._active_by_lease_id[lease_id] = _ActiveProcessRef(
                process_type="asyncio",
                process=process,
                lease=payload,
            )
        return lease_id

    def register_popen_process(
        self,
        *,
        owner_kind: OwnerKind,
        owner_id: str,
        process: PopenProcess,
        request_id: str | None = None,
        run_id: str | None = None,
        attempt_number: int | None = None,
        engine: str | None = None,
        transport: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if not self._enabled():
            return None
        pid = int(process.pid or 0)
        if pid <= 0:
            logger.warning("Process supervisor skipped popen lease registration due to invalid pid")
            return None
        lease_id = str(uuid.uuid4())
        payload = self._new_lease_payload(
            lease_id=lease_id,
            owner_kind=owner_kind,
            owner_id=owner_id,
            pid=pid,
            request_id=request_id,
            run_id=run_id,
            attempt_number=attempt_number,
            engine=engine,
            transport=transport,
            metadata=metadata,
        )
        self._lease_store.upsert_active(payload)
        with self._lock:
            self._active_by_lease_id[lease_id] = _ActiveProcessRef(
                process_type="popen",
                process=process,
                lease=payload,
            )
        return lease_id

    def release(self, lease_id: str | None, *, reason: str = "released") -> None:
        if not lease_id:
            return
        with self._lock:
            self._active_by_lease_id.pop(lease_id, None)
        self._lease_store.close(lease_id, reason=reason)

    async def terminate_lease_async(self, lease_id: str, *, reason: str) -> TerminationResult:
        with self._lock:
            ref = self._active_by_lease_id.get(lease_id)
        if ref is not None:
            if ref.process_type == "asyncio":
                result = await terminate_asyncio_process_tree(ref.process)
            else:
                result = await asyncio.to_thread(terminate_popen_process_tree, ref.process)
            self.release(lease_id, reason=f"{reason}:{result.outcome}")
            return result
        payload = self._lease_store.get(lease_id)
        if not isinstance(payload, dict):
            return TerminationResult(outcome="already_exited", detail="lease_not_found")
        pid_raw = payload.get("pid")
        if not isinstance(pid_raw, int):
            self.release(lease_id, reason=f"{reason}:invalid_pid")
            return TerminationResult(outcome="failed", detail="invalid_pid")
        result = await asyncio.to_thread(terminate_pid_tree, int(pid_raw))
        self.release(lease_id, reason=f"{reason}:{result.outcome}")
        return result

    def terminate_lease_sync(self, lease_id: str, *, reason: str) -> TerminationResult:
        with self._lock:
            ref = self._active_by_lease_id.get(lease_id)
        if ref is not None:
            if ref.process_type == "popen":
                result = terminate_popen_process_tree(ref.process)
            else:
                pid = int(ref.lease.get("pid") or 0)
                result = terminate_pid_tree(pid) if pid > 0 else TerminationResult("failed", "invalid_pid")
            self.release(lease_id, reason=f"{reason}:{result.outcome}")
            return result
        payload = self._lease_store.get(lease_id)
        if not isinstance(payload, dict):
            return TerminationResult(outcome="already_exited", detail="lease_not_found")
        pid_raw = payload.get("pid")
        if not isinstance(pid_raw, int):
            self.release(lease_id, reason=f"{reason}:invalid_pid")
            return TerminationResult(outcome="failed", detail="invalid_pid")
        result = terminate_pid_tree(int(pid_raw))
        self.release(lease_id, reason=f"{reason}:{result.outcome}")
        return result

    async def reap_orphan_leases_on_startup(self) -> list[dict[str, Any]]:
        if not self._enabled():
            return []
        reports: list[dict[str, Any]] = []
        for lease in self._lease_store.list_active():
            lease_id = str(lease.get("lease_id") or "").strip()
            pid_raw = lease.get("pid")
            if not lease_id or not isinstance(pid_raw, int):
                continue
            result = await asyncio.to_thread(terminate_pid_tree, int(pid_raw))
            self._lease_store.close(lease_id, reason=f"startup_orphan_reap:{result.outcome}")
            report = {
                "lease_id": lease_id,
                "owner_kind": lease.get("owner_kind"),
                "owner_id": lease.get("owner_id"),
                "request_id": lease.get("request_id"),
                "run_id": lease.get("run_id"),
                "attempt_number": lease.get("attempt_number"),
                "engine": lease.get("engine"),
                "pid": pid_raw,
                "outcome": result.outcome,
                "detail": result.detail,
            }
            reports.append(report)
        with self._lock:
            self._startup_orphan_reports = list(reports)
        return reports

    def consume_startup_orphan_reports(self) -> list[dict[str, Any]]:
        with self._lock:
            reports = list(self._startup_orphan_reports)
            self._startup_orphan_reports.clear()
        return reports

    def start(self) -> None:
        if not self._enabled():
            return
        if self._sweep_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._sweep_task = loop.create_task(self._sweep_loop())

    async def stop(self) -> None:
        task = self._sweep_task
        self._sweep_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    async def _sweep_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(max(1, int(config.SYSTEM.PROCESS_SWEEP_INTERVAL_SEC)))
                self._sweep_once()
            except asyncio.CancelledError:
                raise
            except (OSError, RuntimeError, ValueError):
                logger.warning("Process supervisor sweep failed", exc_info=True)

    def _sweep_once(self) -> None:
        if not self._enabled():
            return
        closed: list[tuple[str, str]] = []
        with self._lock:
            items = list(self._active_by_lease_id.items())
        for lease_id, ref in items:
            if ref.process_type == "popen":
                rc = ref.process.poll()
                if rc is not None:
                    closed.append((lease_id, f"process_exit:{rc}"))
                    continue
            else:
                if ref.process.returncode is not None:
                    closed.append((lease_id, f"process_exit:{ref.process.returncode}"))
        for lease_id, reason in closed:
            self.release(lease_id, reason=reason)


process_supervisor = RuntimeProcessSupervisor()
