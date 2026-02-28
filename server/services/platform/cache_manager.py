import os
import asyncio
import logging
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from server.config import config

class CacheManager:
    """
    Background service for managing temporary artifacts and caches.
    
    Current Responsibility:
    - Periodically prunes the `uv` cache to free up disk space.
    - Runs `uv cache prune` daily.
    """
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.uv_cache_dir = Path(config.SYSTEM.UV_CACHE_DIR)

    def start(self):
        # Schedule cleanup every day
        self.scheduler.add_job(self.prune_uv_cache, 'interval', days=1)
        self.scheduler.start()

    async def prune_uv_cache(self):
        """Runs 'uv cache prune -v' to clean up dangling cache items."""
        logger.info("Running UV Cache Prune...")
        env = os.environ.copy()
        env["UV_CACHE_DIR"] = str(self.uv_cache_dir)
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "uv", "cache", "prune", "-v",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info("UV Cache Pruned: %s", stdout.decode())
            else:
                logger.warning("UV Cache Prune Failed: %s", stderr.decode())
        except Exception as e:
            logger.exception("Error checking cache")

cache_manager = CacheManager()

logger = logging.getLogger(__name__)
