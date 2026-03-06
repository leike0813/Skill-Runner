import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from server.config import config
from server.services.orchestration.run_store import run_store
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager
from server.services.platform.process_lease_store import process_lease_store


class RunCleanupManager:
    """
    Background service for managing run and cache lifecycle cleanup.

    Responsibilities:
    - Periodically prune run records and directories based on TTL.
    - Delete failed runs immediately.
    - Provide a manual purge API for clearing all cached history.
    """

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        interval_hours = int(config.SYSTEM.RUN_CLEANUP_INTERVAL_HOURS)
        if interval_hours <= 0:
            logger.info("Run cleanup scheduler disabled (interval <= 0)")
            return
        self.scheduler.add_job(self.cleanup_expired_runs, "interval", hours=interval_hours)
        self.scheduler.start()

    async def cleanup_expired_runs(self) -> None:
        retention_days = int(config.SYSTEM.RUN_RETENTION_DAYS)
        if retention_days <= 0:
            logger.info("Run cleanup disabled (retention <= 0)")
            return
        logger.info("Run cleanup started at %s", datetime.utcnow().isoformat())
        candidates = await run_store.list_runs_for_cleanup(retention_days)
        deleted_runs = 0
        deleted_requests = 0
        for row in candidates:
            run_id = row["run_id"]
            request_ids = await run_store.delete_run_records(run_id)
            deleted_requests += len(request_ids)
            workspace_manager.delete_run_dir(run_id)
            deleted_runs += 1
        if deleted_runs or deleted_requests:
            logger.info(
                "Run cleanup removed runs=%s requests=%s",
                deleted_runs,
                deleted_requests
            )
        await self.cleanup_stale_trust_entries()
        await self.cleanup_auxiliary_storage(retention_days)

    async def clear_all(self) -> dict:
        counts = await run_store.clear_all()
        workspace_manager.purge_runs_dir()
        return counts

    async def cleanup_stale_trust_entries(self) -> None:
        active_run_ids = await run_store.list_active_run_ids()
        active_run_dirs = []
        for run_id in active_run_ids:
            run_dir = workspace_manager.get_run_dir(run_id)
            if run_dir:
                active_run_dirs.append(run_dir)
        try:
            run_folder_trust_manager.cleanup_stale_entries(active_run_dirs)
        except (OSError, RuntimeError, ValueError):
            logger.warning("Stale trust cleanup failed", exc_info=True)

    async def cleanup_auxiliary_storage(self, retention_days: int) -> None:
        if retention_days <= 0:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._cleanup_tmp_uploads(cutoff)
        self._cleanup_ui_shell_sessions(cutoff)
        try:
            pruned = process_lease_store.prune_closed_before(cutoff_iso=cutoff_iso)
            if pruned > 0:
                logger.info("Run cleanup pruned closed process leases=%s", pruned)
        except (OSError, RuntimeError, ValueError):
            logger.warning("Process lease pruning failed", exc_info=True)

    @staticmethod
    def _is_entry_expired(path: Path, cutoff: datetime) -> bool:
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return False
        return modified < cutoff

    def _cleanup_tmp_uploads(self, cutoff: datetime) -> None:
        root = Path(config.SYSTEM.TMP_UPLOADS_DIR)
        if not root.exists():
            return
        removed = 0
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if not self._is_entry_expired(entry, cutoff):
                continue
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        if removed > 0:
            logger.info("Run cleanup removed tmp_uploads directories=%s", removed)

    def _cleanup_ui_shell_sessions(self, cutoff: datetime) -> None:
        root = Path(config.SYSTEM.DATA_DIR) / "ui_shell_sessions"
        if not root.exists():
            return
        active_session_dirs: set[str] = set()
        for lease in process_lease_store.list_active():
            if str(lease.get("owner_kind") or "") != "ui_shell":
                continue
            metadata = lease.get("metadata")
            if isinstance(metadata, dict):
                session_dir = metadata.get("session_dir")
                if isinstance(session_dir, str) and session_dir.strip():
                    active_session_dirs.add(str(Path(session_dir).resolve()))
        removed = 0
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if str(entry.resolve()) in active_session_dirs:
                continue
            if not self._is_entry_expired(entry, cutoff):
                continue
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        if removed > 0:
            logger.info("Run cleanup removed ui_shell_sessions directories=%s", removed)


run_cleanup_manager = RunCleanupManager()

logger = logging.getLogger(__name__)
