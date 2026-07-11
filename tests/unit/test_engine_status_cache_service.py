from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from server.services.engine_management.agent_cli_manager import EngineStatus
from server.services.engine_management.engine_status_cache_service import (
    EngineStatusCacheService,
)


class _FakeManager:
    def __init__(self, data_dir: Path) -> None:
        self.profile = SimpleNamespace(data_dir=data_dir)
        self._status = {
            "codex": EngineStatus(present=True, version="0.105.0"),
            "claude": EngineStatus(present=True, version="1.0.0"),
            "opencode": EngineStatus(present=True, version="1.2.15"),
            "qwen": EngineStatus(present=False, version=""),
        }

    def collect_status(self):
        return dict(self._status)

    def collect_engine_status(self, engine: str):
        return self._status[engine]


@pytest.mark.asyncio
async def test_engine_status_cache_service_refresh_all_writes_cache(tmp_path: Path):
    runs_db = tmp_path / "runs.db"
    service = EngineStatusCacheService(_FakeManager(tmp_path), db_path=runs_db)

    snapshot = await service.refresh_all()

    assert snapshot["codex"].version == "0.105.0"
    assert service.db_path == runs_db.resolve()
    with sqlite3.connect(str(service.db_path)) as conn:
        row = conn.execute(
            "SELECT present, version FROM engine_status_cache WHERE engine = ?",
            ("codex",),
        ).fetchone()
    assert row is not None
    assert int(row[0]) == 1
    assert row[1] == "0.105.0"


@pytest.mark.asyncio
async def test_engine_status_cache_service_refresh_engine_merges_existing_cache(tmp_path: Path):
    manager = _FakeManager(tmp_path)
    service = EngineStatusCacheService(manager, db_path=tmp_path / "runs.db")
    await service.refresh_all()

    manager._status["claude"] = EngineStatus(present=True, version="1.1.0")
    refreshed = await service.refresh_engine("claude")

    snapshot = service.get_snapshot()
    assert refreshed.version == "1.1.0"
    assert snapshot["claude"].version == "1.1.0"
    assert snapshot["codex"].version == "0.105.0"


def test_engine_status_cache_service_invalid_cache_degrades_to_empty_snapshot(tmp_path: Path):
    manager = _FakeManager(tmp_path)
    service = EngineStatusCacheService(manager, db_path=tmp_path / "runs.db")
    legacy_path = manager.profile.data_dir / "agent_status.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text("{invalid", encoding="utf-8")

    snapshot = service.get_snapshot()

    assert snapshot["codex"].version is None
    assert snapshot["claude"].version is None


def test_engine_status_cache_service_get_snapshot_does_not_touch_sqlite(tmp_path: Path, monkeypatch):
    service = EngineStatusCacheService(_FakeManager(tmp_path), db_path=tmp_path / "runs.db")

    def _fail_connect(*args, **kwargs):
        _ = args
        _ = kwargs
        raise AssertionError("get_snapshot must not open sqlite connections")

    monkeypatch.setattr(sqlite3, "connect", _fail_connect)

    snapshot = service.get_snapshot()

    assert snapshot["codex"].version is None


@pytest.mark.asyncio
async def test_engine_status_cache_service_migrates_legacy_file_when_db_empty(tmp_path: Path):
    manager = _FakeManager(tmp_path)
    service = EngineStatusCacheService(manager, db_path=tmp_path / "runs.db")
    legacy_path = manager.profile.data_dir / "agent_status.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        '{"codex":{"present":true,"version":"0.201.0"}}\n',
        encoding="utf-8",
    )

    snapshot = await service.load_persisted()

    assert snapshot["codex"].version == "0.201.0"
    with sqlite3.connect(str(service.db_path)) as conn:
        row = conn.execute(
            "SELECT version FROM engine_status_cache WHERE engine = ?",
            ("codex",),
        ).fetchone()
    assert row is not None
    assert row[0] == "0.201.0"


@pytest.mark.asyncio
async def test_engine_status_cache_service_start_stop_scheduler(tmp_path: Path):
    service = EngineStatusCacheService(_FakeManager(tmp_path), db_path=tmp_path / "runs.db")

    service.start()
    assert service._scheduler is not None  # noqa: SLF001
    assert service._scheduler.running is True  # noqa: SLF001

    service.stop()
    assert service._scheduler is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_engine_status_cache_requires_error_free_probe_for_confirmed_present(tmp_path: Path):
    manager = _FakeManager(tmp_path)
    service = EngineStatusCacheService(manager, db_path=tmp_path / "runs.db")
    await service.refresh_all()
    assert service.is_confirmed_present("codex") is True

    def _failed_probe(_engine: str):
        raise RuntimeError("probe unavailable")

    manager.collect_engine_status = _failed_probe
    status = await service.refresh_engine("codex")

    assert status.present is True
    assert status.version == "0.105.0"
    assert status.last_error == "probe unavailable"
    assert service.is_confirmed_present("codex") is False


@pytest.mark.asyncio
async def test_engine_status_cache_adds_last_error_to_existing_table(tmp_path: Path):
    db_path = tmp_path / "runs.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE engine_status_cache (engine TEXT PRIMARY KEY, present INTEGER NOT NULL, version TEXT, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO engine_status_cache VALUES (?, ?, ?, ?)",
            ("codex", 1, "0.105.0", "2026-01-01T00:00:00Z"),
        )
    service = EngineStatusCacheService(_FakeManager(tmp_path), db_path=db_path)

    snapshot = await service.load_persisted()

    assert snapshot["codex"].version == "0.105.0"
    with sqlite3.connect(str(db_path)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(engine_status_cache)")}
    assert "last_error" in columns
