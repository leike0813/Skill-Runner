from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from server.engines.opencode.models.catalog_service import opencode_model_catalog
from server.services.engine_management.engine_catalog import normalize_engine_name


class RuntimeProbeCatalogHandler(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    async def refresh(self, *, reason: str) -> None:
        ...

    def request_refresh_async(self, *, reason: str) -> asyncio.Task[None] | None:
        ...

    def get_snapshot(self) -> dict[str, object]:
        ...

    def cache_path(self) -> Path:
        ...


@dataclass(frozen=True)
class _OpencodeCatalogHandler:
    def start(self) -> None:
        opencode_model_catalog.start()

    def stop(self) -> None:
        opencode_model_catalog.stop()

    async def refresh(self, *, reason: str) -> None:
        await opencode_model_catalog.refresh(reason=reason)

    def request_refresh_async(self, *, reason: str) -> asyncio.Task[None] | None:
        return opencode_model_catalog.request_refresh_async(reason=reason)

    def get_snapshot(self) -> dict[str, object]:
        return opencode_model_catalog.get_snapshot()

    def cache_path(self) -> Path:
        return opencode_model_catalog.cache_path()


class EngineModelCatalogLifecycle:
    def __init__(self) -> None:
        self._handlers: dict[str, RuntimeProbeCatalogHandler] = {
            "opencode": _OpencodeCatalogHandler(),
        }

    def runtime_probe_engines(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def supports_engine(self, engine: str) -> bool:
        return normalize_engine_name(engine) in self._handlers

    def start(self) -> None:
        for handler in self._handlers.values():
            handler.start()

    def stop(self) -> None:
        for handler in self._handlers.values():
            handler.stop()

    async def refresh(self, engine: str, *, reason: str) -> None:
        handler = self._handlers.get(normalize_engine_name(engine))
        if handler is None:
            return
        await handler.refresh(reason=reason)

    def request_refresh_async(self, engine: str, *, reason: str) -> asyncio.Task[None] | None:
        handler = self._handlers.get(normalize_engine_name(engine))
        if handler is None:
            return None
        return handler.request_refresh_async(reason=reason)

    def request_refresh_async_all(self, *, reason: str) -> None:
        for handler in self._handlers.values():
            handler.request_refresh_async(reason=reason)

    def get_snapshot(self, engine: str) -> dict[str, object] | None:
        handler = self._handlers.get(normalize_engine_name(engine))
        if handler is None:
            return None
        return handler.get_snapshot()

    def cache_paths(self) -> tuple[Path, ...]:
        return tuple(handler.cache_path().resolve() for handler in self._handlers.values())


engine_model_catalog_lifecycle = EngineModelCatalogLifecycle()
