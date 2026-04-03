import asyncio
import logging
import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import sys

from server.config import config
from server.models import EngineUpgradeTaskStatus
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.model_registry import model_registry
from server.services.engine_management.engine_status_cache_service import engine_status_cache_service
from server.services.engine_management.engine_upgrade_store import engine_upgrade_store
from server.services.engine_management.runtime_profile import get_runtime_profile

logger = logging.getLogger(__name__)


class EngineUpgradeBusyError(RuntimeError):
    """Raised when another upgrade task is already running."""


class EngineUpgradeValidationError(ValueError):
    """Raised when request payload is invalid."""


class EngineUpgradeManager:
    """Background manager for engine upgrade tasks."""

    SUPPORTED_ENGINES = ("codex", "gemini", "iflow", "opencode", "claude")

    def __init__(self) -> None:
        self._store = engine_upgrade_store
        self._state_lock = threading.Lock()
        self._running_request_id: Optional[str] = None
        self._script_path = Path(config.SYSTEM.ROOT) / "scripts" / "agent_manager.py"
        self._cli_manager = AgentCliManager()

    async def create_task(self, mode: str, requested_engine: Optional[str]) -> str:
        normalized_mode = mode.strip().lower()
        normalized_engine = requested_engine.strip().lower() if requested_engine else None

        if normalized_mode not in {"single", "all"}:
            raise EngineUpgradeValidationError("mode must be 'single' or 'all'")
        if normalized_mode == "single" and not normalized_engine:
            raise EngineUpgradeValidationError("engine is required when mode=single")
        if normalized_mode == "all" and normalized_engine:
            raise EngineUpgradeValidationError("engine must be omitted when mode=all")
        if normalized_engine and normalized_engine not in self.SUPPORTED_ENGINES:
            raise EngineUpgradeValidationError(f"Unsupported engine: {normalized_engine}")

        with self._state_lock:
            if self._running_request_id or await self._store.has_running_task():
                raise EngineUpgradeBusyError("Another engine upgrade task is running")
            request_id = str(uuid.uuid4())
            await self._store.create_task(request_id, normalized_mode, normalized_engine)
            self._running_request_id = request_id

        asyncio.create_task(self._run_task(request_id))
        return request_id

    async def get_task(self, request_id: str) -> Optional[Dict[str, object]]:
        return await self._store.get_task(request_id)

    async def _run_task(self, request_id: str) -> None:
        task = await self._store.get_task(request_id)
        if not task:
            with self._state_lock:
                if self._running_request_id == request_id:
                    self._running_request_id = None
            return

        mode = str(task["mode"])
        requested_engine = task.get("requested_engine")
        engines = self._resolve_engines(mode, requested_engine)
        results: Dict[str, Dict[str, Optional[str]]] = {}

        await self._store.update_task(request_id, status=EngineUpgradeTaskStatus.RUNNING)
        logger.info("Engine upgrade task started: request_id=%s mode=%s", request_id, mode)

        try:
            for engine in engines:
                results[engine] = await self._run_single_engine_task(engine, mode=mode)
                if results[engine]["status"] == "succeeded":
                    await self._refresh_engine_status_cache(engine)
                    self._refresh_engine_model_registry(engine)
            all_success = all(result["status"] == "succeeded" for result in results.values())
            final_status = EngineUpgradeTaskStatus.SUCCEEDED if all_success else EngineUpgradeTaskStatus.FAILED
            await self._store.update_task(request_id, status=final_status, results=results)
            logger.info("Engine upgrade task finished: request_id=%s status=%s", request_id, final_status.value)
        except (OSError, RuntimeError, ValueError, TypeError):
            logger.exception("Engine upgrade task failed unexpectedly: request_id=%s", request_id)
            await self._store.update_task(
                request_id,
                status=EngineUpgradeTaskStatus.FAILED,
                results=results,
            )
        finally:
            with self._state_lock:
                if self._running_request_id == request_id:
                    self._running_request_id = None

    def _resolve_engines(self, mode: str, requested_engine: Optional[object]) -> List[str]:
        if mode == "single":
            if not isinstance(requested_engine, str) or requested_engine not in self.SUPPORTED_ENGINES:
                return []
            return [requested_engine]
        return list(self.SUPPORTED_ENGINES)

    def _resolve_single_engine_action(self, engine: str) -> str:
        managed_cmd = self._cli_manager.resolve_managed_engine_command(engine)
        return "upgrade" if managed_cmd is not None else "install"

    async def _run_single_engine_task(self, engine: str, *, mode: str) -> Dict[str, Optional[str]]:
        action = "upgrade" if mode == "all" else self._resolve_single_engine_action(engine)
        profile = get_runtime_profile()
        if action == "install":
            cmd = [sys.executable, str(self._script_path), "--ensure", "--engines", engine]
        else:
            cmd = [sys.executable, str(self._script_path), "--upgrade-engine", engine]
        env = profile.build_subprocess_env(os.environ.copy())
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(Path(config.SYSTEM.ROOT)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
            if proc.returncode == 0:
                return {
                    "status": "succeeded",
                    "action": action,
                    "stdout": stdout,
                    "stderr": stderr,
                    "error": None,
                }
            return {
                "status": "failed",
                "action": action,
                "stdout": stdout,
                "stderr": stderr,
                "error": f"{action.capitalize()} command exited with code {proc.returncode}",
            }
        except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            logger.exception("Engine %s execution failed for %s", action, engine)
            return {
                "status": "failed",
                "action": action,
                "stdout": "",
                "stderr": "",
                "error": str(exc),
            }

    async def _refresh_engine_status_cache(self, engine: str) -> None:
        try:
            await engine_status_cache_service.refresh_engine(engine)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.warning(
                "Engine version cache refresh failed after upgrade",
                extra={
                    "component": "engine_management.engine_upgrade_manager",
                    "action": "refresh_engine_status_cache",
                    "engine": engine,
                    "error_type": type(exc).__name__,
                    "fallback": "keep_previous_engine_status_cache",
                },
                exc_info=True,
            )

    def _refresh_engine_model_registry(self, engine: str) -> None:
        try:
            if model_registry.supports_runtime_catalog_refresh(engine):
                return
            model_registry.refresh(engine)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.warning(
                "Engine model registry refresh failed after upgrade",
                extra={
                    "component": "engine_management.engine_upgrade_manager",
                    "action": "refresh_engine_model_registry",
                    "engine": engine,
                    "error_type": type(exc).__name__,
                    "fallback": "keep_previous_engine_model_registry_cache",
                },
                exc_info=True,
            )


engine_upgrade_manager = EngineUpgradeManager()
