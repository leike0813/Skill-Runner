import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from ..config import config
from .temp_skill_run_manager import temp_skill_run_manager

logger = logging.getLogger(__name__)


class TempSkillCleanupManager:
    """Scheduled fallback cleanup for orphan temporary skill package files."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._job_added = False

    def start(self) -> None:
        interval_hours = int(config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS)
        if interval_hours <= 0:
            logger.info("Temporary skill cleanup scheduler disabled (interval <= 0)")
            return
        if self.scheduler.running:
            return
        try:
            if not self._job_added:
                self.scheduler.add_job(
                    temp_skill_run_manager.cleanup_orphans, "interval", hours=interval_hours
                )
                self._job_added = True
            self.scheduler.start()
        except RuntimeError:
            # Recreate scheduler if previous event loop was closed (common in repeated TestClient lifespans).
            self.scheduler = AsyncIOScheduler()
            self._job_added = False
            self.scheduler.add_job(
                temp_skill_run_manager.cleanup_orphans, "interval", hours=interval_hours
            )
            self._job_added = True
            self.scheduler.start()


temp_skill_cleanup_manager = TempSkillCleanupManager()
