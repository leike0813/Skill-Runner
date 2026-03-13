"""Lease lifecycle for local runtime process ownership."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from server.config import config
from server.services.engine_management.runtime_profile import get_runtime_profile

logger = logging.getLogger(__name__)

ShutdownCallback = Callable[[str], Awaitable[None] | None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _LeaseRecord:
    owner_id: str | None
    metadata: dict[str, str]
    expires_at: datetime
    first_heartbeat_received: bool


class LocalRuntimeLeaseService:
    """In-memory lease service used by local runtime mode."""

    def __init__(self) -> None:
        ttl = int(getattr(config.SYSTEM, "LOCAL_RUNTIME_LEASE_TTL_SEC", 60))
        self._ttl_seconds = max(10, ttl)
        self._heartbeat_interval_seconds = max(5, min(20, self._ttl_seconds // 3))
        self._first_heartbeat_grace_seconds = max(
            0,
            int(getattr(config.SYSTEM, "LOCAL_RUNTIME_LEASE_FIRST_HEARTBEAT_GRACE_SEC", 15)),
        )
        self._sweep_interval_seconds = max(
            1, int(getattr(config.SYSTEM, "LOCAL_RUNTIME_LEASE_SWEEP_INTERVAL_SEC", 5))
        )
        self._lock = asyncio.Lock()
        self._leases: dict[str, _LeaseRecord] = {}
        self._task: asyncio.Task[None] | None = None
        self._shutdown_callback: ShutdownCallback | None = None
        self._shutdown_requested = False
        self._has_ever_had_lease = False

    def enabled(self) -> bool:
        return get_runtime_profile().mode == "local"

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def heartbeat_interval_seconds(self) -> int:
        return self._heartbeat_interval_seconds

    async def start(self, shutdown_callback: ShutdownCallback) -> None:
        if not self.enabled():
            return
        self._shutdown_callback = shutdown_callback
        if self._task is not None:
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._sweep_loop())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    async def acquire(
        self, *, owner_id: str | None = None, metadata: dict[str, str] | None = None
    ) -> tuple[str, datetime, int]:
        now = _utc_now()
        lease_id = str(uuid.uuid4())
        async with self._lock:
            expires_at = now + timedelta(seconds=self._ttl_seconds)
            self._leases[lease_id] = _LeaseRecord(
                owner_id=owner_id,
                metadata=dict(metadata or {}),
                expires_at=expires_at,
                first_heartbeat_received=False,
            )
            self._shutdown_requested = False
            self._has_ever_had_lease = True
            active = len(self._leases)
        return lease_id, expires_at, active

    async def heartbeat(self, lease_id: str) -> tuple[bool, datetime | None, int]:
        now = _utc_now()
        safe = lease_id.strip()
        if not safe:
            return False, None, await self.active_count()
        async with self._lock:
            self._prune_expired_locked(now)
            lease = self._leases.get(safe)
            if lease is None:
                active = len(self._leases)
                return False, None, active
            lease.expires_at = now + timedelta(seconds=self._ttl_seconds)
            lease.first_heartbeat_received = True
            active = len(self._leases)
            return True, lease.expires_at, active

    async def release(self, lease_id: str) -> tuple[bool, int]:
        safe = lease_id.strip()
        if not safe:
            return False, await self.active_count()
        shutdown_needed = False
        async with self._lock:
            removed = self._leases.pop(safe, None) is not None
            self._prune_expired_locked(_utc_now())
            active = len(self._leases)
            if removed and active == 0 and self._has_ever_had_lease and not self._shutdown_requested:
                self._shutdown_requested = True
                shutdown_needed = True
        if shutdown_needed:
            await self._invoke_shutdown("all_leases_released")
        return removed, active

    async def active_count(self) -> int:
        async with self._lock:
            self._prune_expired_locked(_utc_now())
            return len(self._leases)

    async def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled(),
            "ttl_seconds": self._ttl_seconds,
            "heartbeat_interval_seconds": self._heartbeat_interval_seconds,
            "active_leases": await self.active_count(),
            "has_ever_had_lease": self._has_ever_had_lease,
        }

    def _prune_expired_locked(self, now: datetime) -> None:
        expired = [lease_id for lease_id, lease in self._leases.items() if self._is_expired(lease, now)]
        for lease_id in expired:
            self._leases.pop(lease_id, None)

    def _is_expired(self, lease: _LeaseRecord, now: datetime) -> bool:
        expires_at = lease.expires_at
        if not lease.first_heartbeat_received and self._first_heartbeat_grace_seconds > 0:
            expires_at = expires_at + timedelta(seconds=self._first_heartbeat_grace_seconds)
        return expires_at <= now

    async def _sweep_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._sweep_interval_seconds)
                shutdown_needed = False
                async with self._lock:
                    self._prune_expired_locked(_utc_now())
                    if (
                        self._has_ever_had_lease
                        and not self._leases
                        and not self._shutdown_requested
                    ):
                        self._shutdown_requested = True
                        shutdown_needed = True
                if shutdown_needed:
                    await self._invoke_shutdown("lease_ttl_expired")
            except asyncio.CancelledError:
                raise
            except (OSError, RuntimeError, ValueError):
                logger.warning("Local runtime lease sweep failed", exc_info=True)

    async def _invoke_shutdown(self, reason: str) -> None:
        callback = self._shutdown_callback
        if callback is None:
            return
        logger.info("Local runtime lease requested shutdown: reason=%s", reason)
        result = callback(reason)
        if asyncio.iscoroutine(result):
            await result


local_runtime_lease_service = LocalRuntimeLeaseService()


def serialize_expiry(expires_at: datetime) -> str:
    return _iso(expires_at)
