import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from server.services.engine_management.agent_cli_manager import (
    AgentCliManager,
    ENGINE_PACKAGES,
    EngineStatus,
    format_status_payload,
)

logger = logging.getLogger(__name__)

_CACHE_PARSE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)


def _supported_engines() -> tuple[str, ...]:
    return tuple(ENGINE_PACKAGES.keys())


@dataclass(frozen=True)
class EngineVersionStatus:
    present: bool
    version: str | None


class EngineStatusCacheService:
    def __init__(self, manager: AgentCliManager | None = None) -> None:
        self._manager = manager or AgentCliManager()
        self._write_lock = asyncio.Lock()
        self._scheduler: AsyncIOScheduler | None = None

    @property
    def cache_path(self) -> Path:
        return self._manager.profile.data_dir / "agent_status.json"

    def get_snapshot(self) -> Dict[str, EngineVersionStatus]:
        payload = self._read_payload()
        snapshot: Dict[str, EngineVersionStatus] = {}
        for engine in _supported_engines():
            raw = payload.get(engine, {})
            if not isinstance(raw, dict):
                raw = {}
            present = bool(raw.get("present", False))
            version = raw.get("version")
            snapshot[engine] = EngineVersionStatus(
                present=present,
                version=version if isinstance(version, str) and version.strip() else None,
            )
        return snapshot

    def get_engine_status(self, engine: str) -> EngineVersionStatus:
        return self.get_snapshot().get(engine, EngineVersionStatus(present=False, version=None))

    def get_engine_version(self, engine: str) -> str | None:
        return self.get_engine_status(engine).version

    async def refresh_all(self) -> Dict[str, EngineVersionStatus]:
        status = self._manager.collect_status()
        await self._write_status(status)
        return {
            engine: EngineVersionStatus(present=item.present, version=item.version or None)
            for engine, item in status.items()
        }

    async def refresh_engine(self, engine: str) -> EngineVersionStatus:
        current = self._read_payload()
        status = self._manager.collect_engine_status(engine)
        current[engine] = {"present": status.present, "version": status.version}
        await self._write_payload(current)
        return EngineVersionStatus(present=status.present, version=status.version or None)

    def start(self) -> None:
        if self._scheduler is not None and self._scheduler.running:
            return
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.refresh_all,
            "interval",
            days=1,
            id="engine_status_cache_daily_refresh",
            replace_existing=True,
        )
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.shutdown(wait=False)
        finally:
            self._scheduler = None

    async def _write_status(self, status: Dict[str, EngineStatus]) -> None:
        await self._write_payload(format_status_payload(status))

    async def _write_payload(self, payload: Dict[str, Dict[str, object]]) -> None:
        async with self._write_lock:
            target = self.cache_path
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_path = target.with_suffix(f"{target.suffix}.tmp")
            normalized = {
                engine: {
                    "present": bool(item.get("present", False)),
                    "version": str(item.get("version") or ""),
                }
            for engine, item in payload.items()
            if engine in set(_supported_engines()) and isinstance(item, dict)
            }
            temp_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
            temp_path.replace(target)

    def _read_payload(self) -> Dict[str, Dict[str, object]]:
        cache_path = self.cache_path
        if not cache_path.exists():
            return {}
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except _CACHE_PARSE_EXCEPTIONS as exc:
            logger.warning(
                "engine status cache unreadable; falling back to empty snapshot",
                extra={
                    "component": "engine_management.engine_status_cache_service",
                    "action": "read_payload",
                    "error_type": type(exc).__name__,
                    "fallback": "empty_snapshot",
                },
                exc_info=True,
            )
            return {}
        if not isinstance(payload, dict):
            logger.warning(
                "engine status cache has invalid root payload; falling back to empty snapshot",
                extra={
                    "component": "engine_management.engine_status_cache_service",
                    "action": "read_payload",
                    "fallback": "empty_snapshot",
                },
            )
            return {}
        return {
            str(engine): item
            for engine, item in payload.items()
            if isinstance(engine, str) and isinstance(item, dict)
        }


engine_status_cache_service = EngineStatusCacheService()
