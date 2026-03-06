from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from fastapi import HTTPException  # type: ignore[import-not-found]

from server.services.platform.async_compat import maybe_await
from server.runtime.observability.contracts import RunStorePort, WorkspacePort

class _UnconfiguredRunStore:
    async def get_request(self, request_id: str):
        _ = request_id
        raise RuntimeError("Run source run_store port is not configured")

    async def get_cached_run(self, cache_key: str):
        _ = cache_key
        raise RuntimeError("Run source run_store port is not configured")

    async def get_temp_cached_run(self, cache_key: str):
        _ = cache_key
        raise RuntimeError("Run source run_store port is not configured")

    async def update_request_run_id(self, request_id: str, run_id: str):
        _ = request_id
        _ = run_id
        raise RuntimeError("Run source run_store port is not configured")


class _UnconfiguredWorkspace:
    def get_run_dir(self, run_id: str):
        _ = run_id
        raise RuntimeError("Run source workspace port is not configured")


run_store: RunStorePort | Any = _UnconfiguredRunStore()
workspace_manager: WorkspacePort | Any = _UnconfiguredWorkspace()


def configure_run_source_ports(
    *,
    run_store_backend: RunStorePort | Any,
    workspace_backend: WorkspacePort | Any,
) -> None:
    global run_store, workspace_manager
    run_store = run_store_backend
    workspace_manager = workspace_backend


def _require_run_store():
    return run_store


def _require_workspace():
    return workspace_manager


@dataclass(frozen=True)
class RunSourceCapabilities:
    supports_pending_reply: bool
    supports_event_history: bool
    supports_log_range: bool
    supports_inline_input_create: bool


class RunSourceAdapter(Protocol):
    source: str
    cache_namespace: str
    capabilities: RunSourceCapabilities

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        ...

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        ...

    async def bind_cached_run(self, request_id: str, run_id: str) -> None:
        ...

    async def mark_run_started(self, request_id: str, run_id: str) -> None:
        ...

    async def mark_failed(self, request_id: str, error_message: str) -> None:
        ...

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        ...

    def build_cancel_kwargs(self, request_id: str) -> Dict[str, str]:
        ...


@dataclass(frozen=True)
class InstalledRunSourceAdapter:
    source: str = "installed"
    cache_namespace: str = "cache_entries"
    capabilities: RunSourceCapabilities = RunSourceCapabilities(
        supports_pending_reply=True,
        supports_event_history=True,
        supports_log_range=True,
        supports_inline_input_create=True,
    )

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await maybe_await(_require_run_store().get_request(request_id))

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        return await maybe_await(_require_run_store().get_cached_run(cache_key))

    async def bind_cached_run(self, request_id: str, run_id: str) -> None:
        await maybe_await(_require_run_store().update_request_run_id(request_id, run_id))

    async def mark_run_started(self, request_id: str, run_id: str) -> None:
        await maybe_await(_require_run_store().update_request_run_id(request_id, run_id))

    async def mark_failed(self, request_id: str, error_message: str) -> None:
        # installed source uses run status sidecar + run table for failure persistence.
        _ = error_message
        _ = request_id

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        _ = request_id
        return None

    def build_cancel_kwargs(self, request_id: str) -> Dict[str, str]:
        return {"request_id": request_id}

installed_run_source_adapter = InstalledRunSourceAdapter()


def require_capability(
    source_adapter: RunSourceAdapter,
    *,
    capability: str,
) -> None:
    if not hasattr(source_adapter.capabilities, capability):
        raise HTTPException(status_code=500, detail=f"Unknown source capability: {capability}")
    if getattr(source_adapter.capabilities, capability):
        return
    raise HTTPException(
        status_code=404,
        detail=f"Capability '{capability}' is unavailable for source '{source_adapter.source}'",
    )


async def get_request_and_run_dir(
    source_adapter: RunSourceAdapter,
    request_id: str,
) -> tuple[Dict[str, Any], Path]:
    request_record = await maybe_await(source_adapter.get_request(request_id))
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = _require_workspace().get_run_dir(run_id_obj)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    return request_record, run_dir
