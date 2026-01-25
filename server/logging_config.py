import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from .config import config


def setup_logging() -> None:
    """Configure logging for the service and write logs to file."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logs_dir = Path(config.SYSTEM.DATA_DIR) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = Path(os.environ.get("LOG_FILE", str(logs_dir / "skill_runner.log")))
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
