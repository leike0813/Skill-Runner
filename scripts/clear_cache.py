import os
import logging
from logging.handlers import RotatingFileHandler

from server.services.run_cleanup_manager import run_cleanup_manager

logger = logging.getLogger(__name__)

def clear_cache():
    logger.info("Target: runs.db + data/runs + data/requests")
    confirm = input("Are you sure you want to delete all runs? [y/N] ")
    if confirm.lower() != 'y':
        logger.info("Aborted.")
        return

    logger.info("Cleaning...")
    try:
        counts = run_cleanup_manager.clear_all()
        logger.info(
            "Done. Removed runs=%s requests=%s cache_entries=%s.",
            counts.get("runs", 0),
            counts.get("requests", 0),
            counts.get("cache_entries", 0)
        )
    except Exception:
        logger.exception("Error cleaning cache")

if __name__ == "__main__":
    log_file = os.environ.get("LOG_FILE", "")
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count))
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )
    clear_cache()
