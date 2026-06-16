"""Router for runtime network diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, Request  # type: ignore[import-not-found]

from server.models import RuntimeClientAddressResponse

router = APIRouter(prefix="/runtime/network", tags=["runtime-network"])


@router.get("/client-address", response_model=RuntimeClientAddressResponse)
async def get_runtime_network_client_address(request: Request) -> RuntimeClientAddressResponse:
    client = request.client
    return RuntimeClientAddressResponse(client_ip=client.host if client is not None else None)
