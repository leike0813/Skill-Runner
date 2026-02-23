from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from fastapi import HTTPException  # type: ignore[import-not-found]

from ..models import RunStatus
from .run_store import run_store
from .temp_skill_run_store import temp_skill_run_store
from .workspace_manager import workspace_manager


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

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        ...

    def get_cached_run(self, cache_key: str) -> Optional[str]:
        ...

    def bind_cached_run(self, request_id: str, run_id: str) -> None:
        ...

    def mark_run_started(self, request_id: str, run_id: str) -> None:
        ...

    def mark_failed(self, request_id: str, error_message: str) -> None:
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

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return run_store.get_request(request_id)

    def get_cached_run(self, cache_key: str) -> Optional[str]:
        return run_store.get_cached_run(cache_key)

    def bind_cached_run(self, request_id: str, run_id: str) -> None:
        run_store.update_request_run_id(request_id, run_id)

    def mark_run_started(self, request_id: str, run_id: str) -> None:
        run_store.update_request_run_id(request_id, run_id)

    def mark_failed(self, request_id: str, error_message: str) -> None:
        # installed source uses run status sidecar + run table for failure persistence.
        _ = error_message
        _ = request_id

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        _ = request_id
        return None

    def build_cancel_kwargs(self, request_id: str) -> Dict[str, str]:
        return {"request_id": request_id}


@dataclass(frozen=True)
class TempRunSourceAdapter:
    source: str = "temp"
    cache_namespace: str = "temp_cache_entries"
    capabilities: RunSourceCapabilities = RunSourceCapabilities(
        supports_pending_reply=True,
        supports_event_history=True,
        supports_log_range=True,
        supports_inline_input_create=False,
    )

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return temp_skill_run_store.get_request(request_id)

    def get_cached_run(self, cache_key: str) -> Optional[str]:
        return run_store.get_temp_cached_run(cache_key)

    def bind_cached_run(self, request_id: str, run_id: str) -> None:
        temp_skill_run_store.bind_cached_run(request_id, run_id)
        if run_store.get_request(request_id):
            run_store.update_request_run_id(request_id, run_id)

    def mark_run_started(self, request_id: str, run_id: str) -> None:
        temp_skill_run_store.update_run_started(request_id, run_id)
        if run_store.get_request(request_id):
            run_store.update_request_run_id(request_id, run_id)

    def mark_failed(self, request_id: str, error_message: str) -> None:
        temp_skill_run_store.update_status(
            request_id,
            status=RunStatus.FAILED,
            error=error_message,
        )

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        return request_id

    def build_cancel_kwargs(self, request_id: str) -> Dict[str, str]:
        # Keep both identifiers for shared cancellation flow:
        # - request_id: run_store interactive runtime/state
        # - temp_request_id: temp lifecycle store
        return {"request_id": request_id, "temp_request_id": request_id}


installed_run_source_adapter = InstalledRunSourceAdapter()
temp_run_source_adapter = TempRunSourceAdapter()


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


def get_request_and_run_dir(
    source_adapter: RunSourceAdapter,
    request_id: str,
) -> tuple[Dict[str, Any], Path]:
    request_record = source_adapter.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id_obj)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    return request_record, run_dir
