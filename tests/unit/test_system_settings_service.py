from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.services.platform.system_settings_service import (
    SystemSettingsService,
    SystemSettingsValidationError,
)


def _build_cfg(tmp_path: Path) -> SimpleNamespace:
    data_dir = tmp_path / "data"
    return SimpleNamespace(
        SYSTEM=SimpleNamespace(
            SETTINGS_FILE=str(data_dir / "system_settings.json"),
            SETTINGS_BOOTSTRAP_FILE=str(tmp_path / "bootstrap.json"),
        )
    )


def test_system_settings_service_bootstraps_missing_file(tmp_path: Path):
    cfg = _build_cfg(tmp_path)
    Path(cfg.SYSTEM.SETTINGS_BOOTSTRAP_FILE).write_text(
        json.dumps(
            {
                "version": 1,
                "logging": {
                    "level": "INFO",
                    "format": "text",
                    "retention_days": 7,
                    "dir_max_bytes": 1024,
                },
            }
        ),
        encoding="utf-8",
    )
    service = SystemSettingsService(cfg=cfg)

    settings = service.get_logging_settings()
    settings_file = Path(cfg.SYSTEM.SETTINGS_FILE)

    assert settings.level == "INFO"
    assert settings.format == "text"
    assert settings.retention_days == 7
    assert settings.dir_max_bytes == 1024
    assert settings_file.exists()


def test_system_settings_service_updates_logging_settings_atomically(tmp_path: Path):
    cfg = _build_cfg(tmp_path)
    Path(cfg.SYSTEM.SETTINGS_BOOTSTRAP_FILE).write_text(
        json.dumps(
            {
                "version": 1,
                "logging": {
                    "level": "INFO",
                    "format": "text",
                    "retention_days": 7,
                    "dir_max_bytes": 1024,
                },
            }
        ),
        encoding="utf-8",
    )
    service = SystemSettingsService(cfg=cfg)

    updated = service.update_logging_settings(
        {
            "level": "DEBUG",
            "format": "json",
            "retention_days": 3,
            "dir_max_bytes": 2048,
        }
    )

    payload = json.loads(Path(cfg.SYSTEM.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert updated.level == "DEBUG"
    assert payload["logging"]["format"] == "json"
    assert payload["logging"]["retention_days"] == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"level": "BAD", "format": "text", "retention_days": 7, "dir_max_bytes": 1},
        {"level": "INFO", "format": "bad", "retention_days": 7, "dir_max_bytes": 1},
        {"level": "INFO", "format": "text", "retention_days": 0, "dir_max_bytes": 1},
        {"level": "INFO", "format": "text", "retention_days": 7, "dir_max_bytes": -1},
    ],
)
def test_system_settings_service_rejects_invalid_logging_payload(tmp_path: Path, payload: dict[str, object]):
    cfg = _build_cfg(tmp_path)
    Path(cfg.SYSTEM.SETTINGS_BOOTSTRAP_FILE).write_text(
        json.dumps(
            {
                "version": 1,
                "logging": {
                    "level": "INFO",
                    "format": "text",
                    "retention_days": 7,
                    "dir_max_bytes": 1024,
                },
            }
        ),
        encoding="utf-8",
    )
    service = SystemSettingsService(cfg=cfg)

    with pytest.raises(SystemSettingsValidationError):
        service.update_logging_settings(payload)
