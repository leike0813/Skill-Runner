"""Router for local runtime lease lifecycle control."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException  # type: ignore[import-not-found]

from server.models import (
    LocalLeaseAcquireRequest,
    LocalLeaseAcquireResponse,
    LocalLeaseHeartbeatRequest,
    LocalLeaseHeartbeatResponse,
    LocalLeaseReleaseRequest,
    LocalLeaseReleaseResponse,
    LocalRuntimeStatusResponse,
)
from server.services.platform.local_runtime_lease_service import (
    local_runtime_lease_service,
    serialize_expiry,
)

router = APIRouter(prefix="/local-runtime", tags=["local-runtime"])


def _ensure_local_mode() -> None:
    if local_runtime_lease_service.enabled():
        return
    raise HTTPException(
        status_code=409,
        detail="local-runtime lease APIs are only available when SKILL_RUNNER_RUNTIME_MODE=local",
    )


@router.get("/status", response_model=LocalRuntimeStatusResponse)
async def get_local_runtime_status() -> LocalRuntimeStatusResponse:
    status = await local_runtime_lease_service.status()
    return LocalRuntimeStatusResponse(**status)


@router.post("/lease/acquire", response_model=LocalLeaseAcquireResponse)
async def acquire_local_runtime_lease(
    request: LocalLeaseAcquireRequest,
) -> LocalLeaseAcquireResponse:
    _ensure_local_mode()
    lease_id, expires_at, active = await local_runtime_lease_service.acquire(
        owner_id=request.owner_id,
        metadata=request.metadata,
    )
    return LocalLeaseAcquireResponse(
        lease_id=lease_id,
        ttl_seconds=local_runtime_lease_service.ttl_seconds,
        heartbeat_interval_seconds=local_runtime_lease_service.heartbeat_interval_seconds,
        expires_at=serialize_expiry(expires_at),
        active_leases=active,
    )


@router.post("/lease/heartbeat", response_model=LocalLeaseHeartbeatResponse)
async def heartbeat_local_runtime_lease(
    request: LocalLeaseHeartbeatRequest,
) -> LocalLeaseHeartbeatResponse:
    _ensure_local_mode()
    found, expires_at, active = await local_runtime_lease_service.heartbeat(request.lease_id)
    if not found or expires_at is None:
        raise HTTPException(status_code=404, detail="lease not found or expired")
    return LocalLeaseHeartbeatResponse(
        lease_id=request.lease_id,
        ttl_seconds=local_runtime_lease_service.ttl_seconds,
        expires_at=serialize_expiry(expires_at),
        active_leases=active,
    )


@router.post("/lease/release", response_model=LocalLeaseReleaseResponse)
async def release_local_runtime_lease(
    request: LocalLeaseReleaseRequest,
) -> LocalLeaseReleaseResponse:
    _ensure_local_mode()
    released, active = await local_runtime_lease_service.release(request.lease_id)
    return LocalLeaseReleaseResponse(
        released=released,
        lease_id=request.lease_id,
        active_leases=active,
    )
