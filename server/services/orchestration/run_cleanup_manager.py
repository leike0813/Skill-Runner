import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from server.config import config
from server.services.orchestration.run_store import run_store
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager


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
        candidates = run_store.list_runs_for_cleanup(retention_days)
        deleted_runs = 0
        deleted_requests = 0
        for row in candidates:
            run_id = row["run_id"]
            request_ids = run_store.delete_run_records(run_id)
            for request_id in request_ids:
                workspace_manager.delete_request_dir(request_id)
                deleted_requests += 1
            workspace_manager.delete_run_dir(run_id)
            deleted_runs += 1
        if deleted_runs or deleted_requests:
            logger.info(
                "Run cleanup removed runs=%s requests=%s",
                deleted_runs,
                deleted_requests
            )
        await self.cleanup_stale_trust_entries()

    def clear_all(self) -> dict:
        request_ids = run_store.list_request_ids()
        counts = run_store.clear_all()
        for request_id in request_ids:
            workspace_manager.delete_request_dir(request_id)
        workspace_manager.purge_runs_dir()
        workspace_manager.purge_requests_dir()
        return counts

    async def cleanup_stale_trust_entries(self) -> None:
        active_run_ids = run_store.list_active_run_ids()
        active_run_dirs = []
        for run_id in active_run_ids:
            run_dir = workspace_manager.get_run_dir(run_id)
            if run_dir:
                active_run_dirs.append(run_dir)
        try:
            run_folder_trust_manager.cleanup_stale_entries(active_run_dirs)
        except Exception:
            logger.warning("Stale trust cleanup failed", exc_info=True)


run_cleanup_manager = RunCleanupManager()

logger = logging.getLogger(__name__)
