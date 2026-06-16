"""Models for runtime network diagnostic APIs."""

from __future__ import annotations

from pydantic import BaseModel


class RuntimeClientAddressResponse(BaseModel):
    """Response payload for the backend-observed client address."""

    client_ip: str | None
