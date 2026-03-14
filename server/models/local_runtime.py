"""Models for local-runtime lease lifecycle APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LocalLeaseAcquireRequest(BaseModel):
    """Request payload for acquiring a local runtime lease."""

    owner_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class LocalLeaseAcquireResponse(BaseModel):
    """Response payload for local runtime lease acquire."""

    lease_id: str
    ttl_seconds: int
    heartbeat_interval_seconds: int
    expires_at: str
    active_leases: int


class LocalLeaseHeartbeatRequest(BaseModel):
    """Request payload for lease heartbeat."""

    lease_id: str


class LocalLeaseHeartbeatResponse(BaseModel):
    """Response payload for lease heartbeat."""

    lease_id: str
    ttl_seconds: int
    expires_at: str
    active_leases: int


class LocalLeaseReleaseRequest(BaseModel):
    """Request payload for lease release."""

    lease_id: str


class LocalLeaseReleaseResponse(BaseModel):
    """Response payload for lease release."""

    released: bool
    lease_id: str
    active_leases: int


class LocalRuntimeStatusResponse(BaseModel):
    """Status payload for local runtime lease manager."""

    enabled: bool
    ttl_seconds: int
    heartbeat_interval_seconds: int
    active_leases: int
    has_ever_had_lease: bool
