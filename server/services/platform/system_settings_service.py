from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, cast

from ...config import config


_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
_LOG_FORMATS = {"text", "json"}


class SystemSettingsValidationError(ValueError):
    """Raised when persisted settings do not satisfy the supported schema."""


@dataclass(frozen=True)
class EditableLoggingSettings:
    level: str
    format: str
    retention_days: int
    dir_max_bytes: int

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


class SystemSettingsService:
    def __init__(self, cfg: Any = config) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()

    @property
    def settings_file(self) -> Path:
        return Path(self._cfg.SYSTEM.SETTINGS_FILE).resolve()

    @property
    def bootstrap_file(self) -> Path:
        return Path(self._cfg.SYSTEM.SETTINGS_BOOTSTRAP_FILE).resolve()

    def _default_payload(self) -> dict[str, Any]:
        bootstrap_payload = self._load_json(self.bootstrap_file)
        return {
            "version": int(bootstrap_payload.get("version", 1)),
            "logging": self._validate_logging_payload(bootstrap_payload.get("logging")),
        }

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemSettingsValidationError("settings payload must be an object")
        return payload

    def ensure_initialized(self) -> Path:
        settings_file = self.settings_file
        if settings_file.exists():
            return settings_file
        with self._lock:
            if settings_file.exists():
                return settings_file
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            payload = self._default_payload()
            self._atomic_write_json(settings_file, payload)
        return settings_file

    def _read_settings_payload(self) -> dict[str, Any]:
        path = self.ensure_initialized()
        payload = self._load_json(path)
        payload.setdefault("version", 1)
        payload["logging"] = self._validate_logging_payload(payload.get("logging"))
        return payload

    def get_logging_settings(self) -> EditableLoggingSettings:
        payload = self._read_settings_payload()
        logging_payload = payload["logging"]
        return EditableLoggingSettings(
            level=logging_payload["level"],
            format=logging_payload["format"],
            retention_days=logging_payload["retention_days"],
            dir_max_bytes=logging_payload["dir_max_bytes"],
        )

    def update_logging_settings(self, updates: Mapping[str, Any]) -> EditableLoggingSettings:
        payload = self._read_settings_payload()
        payload["logging"] = self._validate_logging_payload(updates)
        with self._lock:
            self._atomic_write_json(self.settings_file, payload)
        return self.get_logging_settings()

    @staticmethod
    def _validate_logging_payload(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise SystemSettingsValidationError("logging settings must be an object")

        level_raw = str(raw.get("level", "")).strip().upper()
        if level_raw not in _LOG_LEVELS:
            raise SystemSettingsValidationError("logging.level must be a valid log level")

        format_raw = str(raw.get("format", "")).strip().lower()
        if format_raw not in _LOG_FORMATS:
            raise SystemSettingsValidationError("logging.format must be 'text' or 'json'")

        retention_value = raw.get("retention_days")
        try:
            retention_days = int(cast(Any, retention_value))
        except (TypeError, ValueError) as exc:
            raise SystemSettingsValidationError("logging.retention_days must be an integer") from exc
        if retention_days < 1:
            raise SystemSettingsValidationError("logging.retention_days must be >= 1")

        dir_max_bytes_value = raw.get("dir_max_bytes")
        try:
            dir_max_bytes = int(cast(Any, dir_max_bytes_value))
        except (TypeError, ValueError) as exc:
            raise SystemSettingsValidationError("logging.dir_max_bytes must be an integer") from exc
        if dir_max_bytes < 0:
            raise SystemSettingsValidationError("logging.dir_max_bytes must be >= 0")

        return {
            "level": level_raw,
            "format": format_raw,
            "retention_days": retention_days,
            "dir_max_bytes": dir_max_bytes,
        }

    @staticmethod
    def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)


system_settings_service = SystemSettingsService()
