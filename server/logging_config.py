from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from pathlib import Path

from .config import config
from .runtime.logging.run_context import install_log_record_factory_once
from .services.platform.system_settings_service import system_settings_service

_LOGGING_CONFIGURED_ATTR = "_skill_runner_logging_configured"
_MANAGED_HANDLER_ATTR = "_skill_runner_managed_handler"


@dataclass(frozen=True)
class LoggingSettings:
    level: int
    log_dir: Path
    file_basename: str
    output_format: str
    rotation_when: str
    rotation_interval: int
    retention_days: int
    dir_max_bytes: int


class JsonFormatter(logging.Formatter):
    """Structured formatter for JSON log output."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info
        return json.dumps(payload, ensure_ascii=False)


class QuotaTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Timed rotating file handler with post-rollover quota enforcement."""

    def __init__(
        self,
        *,
        log_file: Path,
        log_dir: Path,
        when: str,
        interval: int,
        backup_count: int,
        dir_max_bytes: int,
    ) -> None:
        self._log_dir = log_dir
        self._dir_max_bytes = dir_max_bytes
        super().__init__(
            filename=str(log_file),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding="utf-8",
        )

    def doRollover(self) -> None:  # noqa: N802 - signature inherited from stdlib
        super().doRollover()
        enforce_log_dir_quota(
            log_dir=self._log_dir,
            active_log=Path(self.baseFilename),
            max_bytes=self._dir_max_bytes,
        )


def _positive_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _non_negative_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _resolve_level(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    candidate = getattr(logging, raw.strip().upper(), None)
    if isinstance(candidate, int):
        return candidate
    return default


def _resolve_apscheduler_level(root_level: int) -> int:
    if root_level <= logging.DEBUG:
        return logging.INFO
    return logging.WARNING


def _resolve_runtime_log_dir() -> Path:
    return Path(os.environ.get("LOG_DIR", str(config.SYSTEM.LOGGING.DIR)))


def _resolve_runtime_file_basename() -> str:
    file_basename = os.environ.get("LOG_FILE_BASENAME", str(config.SYSTEM.LOGGING.FILE_BASENAME)).strip()
    file_basename = file_basename or "skill_runner.log"
    legacy_log_file = os.environ.get("LOG_FILE")
    if legacy_log_file:
        legacy_path = Path(legacy_log_file)
        if legacy_path.name:
            return legacy_path.name
    return file_basename


def _resolve_runtime_rotation_when() -> str:
    return os.environ.get("LOG_ROTATION_WHEN", str(config.SYSTEM.LOGGING.ROTATION_WHEN))


def _resolve_runtime_rotation_interval() -> int:
    return _positive_int(
        os.environ.get("LOG_ROTATION_INTERVAL"),
        int(config.SYSTEM.LOGGING.ROTATION_INTERVAL),
    )


def _resolve_editable_logging_settings() -> tuple[str, str, int, int]:
    editable = system_settings_service.get_logging_settings()
    return (
        editable.level,
        editable.format,
        editable.retention_days,
        editable.dir_max_bytes,
    )


def _resolve_logging_settings() -> LoggingSettings:
    logging_cfg = config.SYSTEM.LOGGING
    editable_level, output_format, retention_days, dir_max_bytes = _resolve_editable_logging_settings()
    level = _resolve_level(editable_level, logging.INFO)

    log_dir = _resolve_runtime_log_dir()
    file_basename = _resolve_runtime_file_basename()
    legacy_log_file = os.environ.get("LOG_FILE")
    if legacy_log_file:
        legacy_path = Path(legacy_log_file)
        if legacy_path.name:
            log_dir = legacy_path.parent
            file_basename = legacy_path.name

    if output_format not in {"text", "json"}:
        output_format = str(logging_cfg.FORMAT).strip().lower() or "text"

    rotation_when = _resolve_runtime_rotation_when()
    rotation_interval = _resolve_runtime_rotation_interval()

    return LoggingSettings(
        level=level,
        log_dir=log_dir,
        file_basename=file_basename,
        output_format=output_format,
        rotation_when=rotation_when,
        rotation_interval=rotation_interval,
        retention_days=retention_days,
        dir_max_bytes=dir_max_bytes,
    )


def get_logging_settings_payload() -> dict[str, dict[str, object]]:
    editable = system_settings_service.get_logging_settings()
    runtime_log_dir = _resolve_runtime_log_dir()
    legacy_log_file = os.environ.get("LOG_FILE")
    file_basename = _resolve_runtime_file_basename()
    if legacy_log_file:
        legacy_path = Path(legacy_log_file)
        if legacy_path.name:
            runtime_log_dir = legacy_path.parent
            file_basename = legacy_path.name
    return {
        "editable": editable.to_payload(),
        "read_only": {
            "dir": str(runtime_log_dir),
            "file_basename": file_basename,
            "rotation_when": _resolve_runtime_rotation_when(),
            "rotation_interval": _resolve_runtime_rotation_interval(),
        },
    }


def _build_formatter(output_format: str) -> logging.Formatter:
    if output_format == "json":
        return JsonFormatter()
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _iter_log_files(log_dir: Path, active_log: Path) -> list[Path]:
    if not log_dir.exists():
        return []
    active_name = active_log.name
    prefix = f"{active_name}."
    files: list[Path] = []
    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        if path.name == active_name or path.name.startswith(prefix):
            files.append(path)
    return files


def enforce_log_dir_quota(
    *,
    log_dir: Path,
    active_log: Path,
    max_bytes: int,
    logger: logging.Logger | None = None,
) -> int:
    """Enforce directory byte quota for the active app log family."""
    if max_bytes <= 0:
        return 0

    files = _iter_log_files(log_dir=log_dir, active_log=active_log)
    size_map: dict[Path, int] = {}
    total_bytes = 0
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        size_map[path] = size
        total_bytes += size

    if total_bytes <= max_bytes:
        return 0

    archives: list[Path] = [p for p in size_map if p.name != active_log.name]
    archives.sort(key=lambda p: p.stat().st_mtime)

    deleted = 0
    for archive in archives:
        if total_bytes <= max_bytes:
            break
        try:
            archive.unlink()
        except OSError as exc:
            if logger is not None:
                logger.warning(
                    "component=logging action=quota_evict error_type=%s target=%s fallback=keep_file",
                    type(exc).__name__,
                    archive.name,
                )
            continue
        total_bytes -= size_map.get(archive, 0)
        deleted += 1

    if total_bytes > max_bytes and logger is not None:
        logger.warning(
            "component=logging action=quota_enforce error_type=QuotaExceeded "
            "fallback=keep_active_log remaining_bytes=%d quota_bytes=%d",
            total_bytes,
            max_bytes,
        )

    return deleted


def _mark_managed_handler(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _MANAGED_HANDLER_ATTR, True)
    return handler


def _remove_managed_handlers(root_logger: logging.Logger) -> None:
    for handler in list(root_logger.handlers):
        if not getattr(handler, _MANAGED_HANDLER_ATTR, False):
            continue
        root_logger.removeHandler(handler)
        handler.close()


def _configure_logging(*, force: bool) -> None:
    install_log_record_factory_once()
    settings = _resolve_logging_settings()

    root_logger = logging.getLogger()
    if getattr(root_logger, _LOGGING_CONFIGURED_ATTR, False) and not force:
        return

    if force:
        _remove_managed_handlers(root_logger)

    formatter = _build_formatter(settings.output_format)

    stream_handler = _mark_managed_handler(logging.StreamHandler())
    stream_handler.setLevel(settings.level)
    stream_handler.setFormatter(formatter)
    root_logger.setLevel(settings.level)
    root_logger.addHandler(stream_handler)

    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = settings.log_dir / settings.file_basename
        file_handler = _mark_managed_handler(
            QuotaTimedRotatingFileHandler(
                log_file=log_file,
                log_dir=settings.log_dir,
                when=settings.rotation_when,
                interval=settings.rotation_interval,
                backup_count=settings.retention_days,
                dir_max_bytes=settings.dir_max_bytes,
            )
        )
        file_handler.setLevel(settings.level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        enforce_log_dir_quota(
            log_dir=settings.log_dir,
            active_log=log_file,
            max_bytes=settings.dir_max_bytes,
            logger=root_logger,
        )
    except OSError as exc:
        root_logger.warning(
            "component=logging action=file_handler_setup error_type=%s fallback=stream_only detail=%s",
            type(exc).__name__,
            str(exc),
        )

    logging.getLogger("apscheduler").setLevel(_resolve_apscheduler_level(settings.level))
    setattr(root_logger, _LOGGING_CONFIGURED_ATTR, True)


def setup_logging() -> None:
    """Configure logging for the service and write logs to file."""
    _configure_logging(force=False)


def reload_logging_from_settings() -> None:
    """Reapply managed logging handlers using the latest persisted settings."""
    _configure_logging(force=True)
