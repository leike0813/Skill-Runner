import asyncio
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import sys

from server.config import config
from server.models import EngineUpgradeTaskStatus
from server.services.orchestration.engine_upgrade_store import engine_upgrade_store
from server.services.orchestration.runtime_profile import get_runtime_profile

logger = logging.getLogger(__name__)


class EngineUpgradeBusyError(RuntimeError):
    """Raised when another upgrade task is already running."""


class EngineUpgradeValidationError(ValueError):
    """Raised when request payload is invalid."""


class EngineUpgradeManager:
    """Background manager for engine upgrade tasks."""

    SUPPORTED_ENGINES = ("codex", "gemini", "iflow", "opencode")

    def __init__(self) -> None:
        self._store = engine_upgrade_store
        self._state_lock = threading.Lock()
        self._running_request_id: Optional[str] = None
        self._script_path = Path(config.SYSTEM.ROOT) / "scripts" / "agent_manager.py"

    def create_task(self, mode: str, requested_engine: Optional[str]) -> str:
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
            if self._running_request_id or self._store.has_running_task():
                raise EngineUpgradeBusyError("Another engine upgrade task is running")
            request_id = str(uuid.uuid4())
            self._store.create_task(request_id, normalized_mode, normalized_engine)
            self._running_request_id = request_id

        asyncio.create_task(self._run_task(request_id))
        return request_id

    def get_task(self, request_id: str) -> Optional[Dict[str, object]]:
        return self._store.get_task(request_id)

    async def _run_task(self, request_id: str) -> None:
        task = self._store.get_task(request_id)
        if not task:
            with self._state_lock:
                if self._running_request_id == request_id:
                    self._running_request_id = None
            return

        mode = str(task["mode"])
        requested_engine = task.get("requested_engine")
        engines = self._resolve_engines(mode, requested_engine)
        results: Dict[str, Dict[str, Optional[str]]] = {}

        self._store.update_task(request_id, status=EngineUpgradeTaskStatus.RUNNING)
        logger.info("Engine upgrade task started: request_id=%s mode=%s", request_id, mode)

        try:
            for engine in engines:
                results[engine] = await self._run_single_engine_upgrade(engine)
            all_success = all(result["status"] == "succeeded" for result in results.values())
            final_status = EngineUpgradeTaskStatus.SUCCEEDED if all_success else EngineUpgradeTaskStatus.FAILED
            self._store.update_task(request_id, status=final_status, results=results)
            logger.info("Engine upgrade task finished: request_id=%s status=%s", request_id, final_status.value)
        except Exception:
            logger.exception("Engine upgrade task failed unexpectedly: request_id=%s", request_id)
            self._store.update_task(
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

    async def _run_single_engine_upgrade(self, engine: str) -> Dict[str, Optional[str]]:
        profile = get_runtime_profile()
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
                    "stdout": stdout,
                    "stderr": stderr,
                    "error": None,
                }
            return {
                "status": "failed",
                "stdout": stdout,
                "stderr": stderr,
                "error": f"Upgrade command exited with code {proc.returncode}",
            }
        except Exception as exc:
            logger.exception("Engine upgrade execution failed for %s", engine)
            return {
                "status": "failed",
                "stdout": "",
                "stderr": "",
                "error": str(exc),
            }


engine_upgrade_manager = EngineUpgradeManager()
