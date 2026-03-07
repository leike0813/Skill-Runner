from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.services.platform.system_log_explorer_service import SystemLogExplorerService


def _mock_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        SYSTEM=SimpleNamespace(
            DATA_DIR=str(tmp_path / "data"),
            LOGGING=SimpleNamespace(
                DIR=str(tmp_path / "logs"),
                FILE_BASENAME="skill_runner.log",
            ),
        )
    )


def test_query_system_logs_filters_level_and_keyword(monkeypatch, tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "skill_runner.log").write_text(
        "\n".join(
            [
                "2026-03-07 01:20:52 ERROR server.test: Failed to install codex",
                "2026-03-07 01:20:53 INFO server.test: Startup complete",
                '{"timestamp":"2026-03-07T01:20:54Z","level":"ERROR","message":"Failed to install gemini"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.services.platform.system_log_explorer_service.config",
        _mock_config(tmp_path),
    )

    service = SystemLogExplorerService()
    payload = service.query(
        source="system",
        cursor=0,
        limit=50,
        q="install",
        level="ERROR",
        from_ts=None,
        to_ts=None,
    )

    assert payload["source"] == "system"
    assert payload["total_matched"] == 2
    assert payload["next_cursor"] is None
    assert all(item["level"] == "ERROR" for item in payload["items"])


def test_query_bootstrap_logs_applies_time_filter(monkeypatch, tmp_path: Path):
    bootstrap_dir = tmp_path / "data" / "logs"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    (bootstrap_dir / "bootstrap.log").write_text(
        "\n".join(
            [
                "ts=2026-03-07T00:00:00Z event=bootstrap.start phase=container_start outcome=running",
                "ts=2026-03-07T00:10:00Z event=agent.ensure.done phase=agent_ensure outcome=ok",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.services.platform.system_log_explorer_service.config",
        _mock_config(tmp_path),
    )

    service = SystemLogExplorerService()
    payload = service.query(
        source="bootstrap",
        cursor=0,
        limit=50,
        q=None,
        level="INFO",
        from_ts=datetime(2026, 3, 7, 0, 5, 0, tzinfo=timezone.utc),
        to_ts=datetime(2026, 3, 7, 0, 30, 0, tzinfo=timezone.utc),
    )

    assert payload["source"] == "bootstrap"
    assert payload["total_matched"] == 1
    assert payload["items"][0]["message"] == "agent.ensure.done"


def test_query_logs_rejects_unknown_source():
    service = SystemLogExplorerService()
    with pytest.raises(ValueError, match="source must be one of"):
        service.query(
            source="other",
            cursor=0,
            limit=10,
            q=None,
            level=None,
            from_ts=None,
            to_ts=None,
        )
