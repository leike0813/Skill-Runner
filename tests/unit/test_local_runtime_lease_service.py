from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from server.services.platform import local_runtime_lease_service as lease_module


def _build_service(monkeypatch: pytest.MonkeyPatch) -> lease_module.LocalRuntimeLeaseService:
    monkeypatch.setattr(
        lease_module,
        "config",
        SimpleNamespace(
            SYSTEM=SimpleNamespace(
                LOCAL_RUNTIME_LEASE_TTL_SEC=60,
                LOCAL_RUNTIME_LEASE_FIRST_HEARTBEAT_GRACE_SEC=15,
                LOCAL_RUNTIME_LEASE_SWEEP_INTERVAL_SEC=5,
            )
        ),
    )
    return lease_module.LocalRuntimeLeaseService()


@pytest.mark.asyncio
async def test_first_heartbeat_grace_window_prevents_early_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service(monkeypatch)
    lease_id, expires_at, _ = await service.acquire(owner_id="pytest")

    service._prune_expired_locked(expires_at + timedelta(seconds=14))  # noqa: SLF001
    assert lease_id in service._leases  # noqa: SLF001

    service._prune_expired_locked(expires_at + timedelta(seconds=16))  # noqa: SLF001
    assert lease_id not in service._leases  # noqa: SLF001


@pytest.mark.asyncio
async def test_heartbeat_after_first_renew_uses_regular_ttl_without_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service(monkeypatch)
    lease_id, _, _ = await service.acquire(owner_id="pytest")
    found, expires_at, _ = await service.heartbeat(lease_id)
    assert found is True
    assert expires_at is not None

    service._prune_expired_locked(expires_at + timedelta(seconds=1))  # noqa: SLF001
    assert lease_id not in service._leases  # noqa: SLF001

