from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Optional

from server.config import config

DEFAULT_MAX_BYTES = int(config.SYSTEM.RUN_AUDIT_SERVICE_LOG_MAX_BYTES)
DEFAULT_BACKUP_COUNT = int(config.SYSTEM.RUN_AUDIT_SERVICE_LOG_BACKUP_COUNT)


class _RunAttemptFilter(logging.Filter):
    def __init__(
        self,
        *,
        run_id: str,
        attempt_number: int,
        strict_attempt_match: bool = True,
    ) -> None:
        super().__init__()
        self._run_id = run_id
        self._attempt_number = attempt_number
        self._strict_attempt_match = strict_attempt_match

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "run_id", None) != self._run_id:
            return False
        if self._strict_attempt_match and getattr(record, "attempt_number", None) != self._attempt_number:
            return False
        return True


class RunServiceLogMirrorSession:
    def __init__(
        self,
        *,
        root_logger: logging.Logger,
        handler: logging.Handler,
    ) -> None:
        self._root_logger = root_logger
        self._handler = handler
        self._closed = False

    def __enter__(self) -> "RunServiceLogMirrorSession":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._root_logger.removeHandler(self._handler)
        self._handler.close()

    @classmethod
    def open_attempt_scope(
        cls,
        *,
        run_dir: Path,
        run_id: str,
        attempt_number: int,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        strict_attempt_match: bool = True,
    ) -> "RunServiceLogMirrorSession":
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        log_path = audit_dir / f"service.{attempt_number}.log"

        handler = RotatingFileHandler(
            filename=log_path,
            mode="a",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.NOTSET)
        handler.addFilter(
            _RunAttemptFilter(
                run_id=run_id,
                attempt_number=attempt_number,
                strict_attempt_match=strict_attempt_match,
            )
        )
        handler.setFormatter(
            logging.Formatter(
                fmt=(
                    "%(asctime)s %(levelname)s %(name)s "
                    "[run_id=%(run_id)s request_id=%(request_id)s attempt=%(attempt_number)s] "
                    "%(message)s"
                ),
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        return cls(root_logger=root_logger, handler=handler)

    @classmethod
    def open_run_scope(
        cls,
        *,
        run_dir: Path,
        run_id: str,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> "RunServiceLogMirrorSession":
        audit_dir = run_dir / ".audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        log_path = audit_dir / "service.run.log"

        handler = RotatingFileHandler(
            filename=log_path,
            mode="a",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.NOTSET)
        handler.addFilter(
            _RunAttemptFilter(
                run_id=run_id,
                attempt_number=1,
                strict_attempt_match=False,
            )
        )
        handler.setFormatter(
            logging.Formatter(
                fmt=(
                    "%(asctime)s %(levelname)s %(name)s "
                    "[run_id=%(run_id)s request_id=%(request_id)s attempt=%(attempt_number)s] "
                    "%(message)s"
                ),
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        return cls(root_logger=root_logger, handler=handler)

    @classmethod
    def open(
        cls,
        *,
        run_dir: Path,
        run_id: str,
        attempt_number: int,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        strict_attempt_match: bool = True,
    ) -> "RunServiceLogMirrorSession":
        return cls.open_attempt_scope(
            run_dir=run_dir,
            run_id=run_id,
            attempt_number=attempt_number,
            max_bytes=max_bytes,
            backup_count=backup_count,
            strict_attempt_match=strict_attempt_match,
        )
