import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from server.config import config
from server.services.orchestration.run_cleanup_manager import RunCleanupManager
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.workspace_manager import workspace_manager
from server.models import RunCreateRequest, RunStatus, SkillManifest


@pytest.fixture(autouse=True)
def _allow_cleanup_skill(monkeypatch, tmp_path):
    skill = SkillManifest(
        id="s",
        name="s",
        engines=["gemini"],
        path=tmp_path
    )
    monkeypatch.setattr(
        "server.services.skill.skill_registry.skill_registry.get_skill",
        lambda skill_id: skill if skill_id == "s" else None
    )
    class NoopTrustManager:
        def cleanup_stale_entries(self, _active_run_dirs):
            return None

    monkeypatch.setattr(
        "server.services.orchestration.run_cleanup_manager.run_folder_trust_manager",
        NoopTrustManager()
    )


def _set_run_row(store: RunStore, run_id: str, status: str, created_at: str) -> None:
    with store._connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, created_at = ? WHERE run_id = ?",
            (status, created_at, run_id)
        )


@pytest.mark.asyncio
async def test_cleanup_expired_runs_removes_failed_and_old(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    now = datetime.utcnow()
    old_ts = (now - timedelta(days=2)).isoformat()
    current_ts = now.isoformat()

    run_old = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    run_failed = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    run_running = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))

    store.create_run(run_old.run_id, cache_key="k1", status=RunStatus.SUCCEEDED)
    store.create_run(run_failed.run_id, cache_key="k2", status=RunStatus.FAILED)
    store.create_run(run_running.run_id, cache_key="k3", status=RunStatus.RUNNING)

    _set_run_row(store, run_old.run_id, RunStatus.SUCCEEDED, old_ts)
    _set_run_row(store, run_failed.run_id, RunStatus.FAILED, current_ts)
    _set_run_row(store, run_running.run_id, RunStatus.RUNNING, current_ts)

    for idx, run_id in enumerate([run_old.run_id, run_failed.run_id, run_running.run_id], start=1):
        request_id = f"request-{idx}"
        workspace_manager.create_request(request_id, {"skill_id": "s"})
        store.create_request(
            request_id=request_id,
            skill_id="s",
            engine="gemini",
            parameter={},
            engine_options={},
            runtime_options={}
        )
        store.update_request_run_id(request_id, run_id)

    old_retention = config.SYSTEM.RUN_RETENTION_DAYS
    config.defrost()
    config.SYSTEM.RUN_RETENTION_DAYS = 1
    config.freeze()
    try:
        await manager.cleanup_expired_runs()
    finally:
        config.defrost()
        config.SYSTEM.RUN_RETENTION_DAYS = old_retention
        config.freeze()

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert not (runs_dir / run_old.run_id).exists()
    assert not (runs_dir / run_failed.run_id).exists()
    assert (runs_dir / run_running.run_id).exists()

    with store._connect() as conn:
        remaining = {row["run_id"] for row in conn.execute("SELECT run_id FROM runs")}
    assert run_running.run_id in remaining
    assert run_old.run_id not in remaining
    assert run_failed.run_id not in remaining


@pytest.mark.asyncio
async def test_cleanup_skips_queued_and_running(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    old_ts = (datetime.utcnow() - timedelta(days=3)).isoformat()
    run_running = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    run_queued = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))

    store.create_run(run_running.run_id, cache_key="k1", status=RunStatus.RUNNING)
    store.create_run(run_queued.run_id, cache_key="k2", status=RunStatus.QUEUED)
    _set_run_row(store, run_running.run_id, RunStatus.RUNNING, old_ts)
    _set_run_row(store, run_queued.run_id, RunStatus.QUEUED, old_ts)

    old_retention = config.SYSTEM.RUN_RETENTION_DAYS
    config.defrost()
    config.SYSTEM.RUN_RETENTION_DAYS = 1
    config.freeze()
    try:
        await manager.cleanup_expired_runs()
    finally:
        config.defrost()
        config.SYSTEM.RUN_RETENTION_DAYS = old_retention
        config.freeze()

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert (runs_dir / run_running.run_id).exists()
    assert (runs_dir / run_queued.run_id).exists()


@pytest.mark.asyncio
async def test_cleanup_handles_invalid_timestamp(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    run_bad = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    store.create_run(run_bad.run_id, cache_key="k1", status=RunStatus.SUCCEEDED)
    _set_run_row(store, run_bad.run_id, RunStatus.SUCCEEDED, "bad-timestamp")

    old_retention = config.SYSTEM.RUN_RETENTION_DAYS
    config.defrost()
    config.SYSTEM.RUN_RETENTION_DAYS = 1
    config.freeze()
    try:
        await manager.cleanup_expired_runs()
    finally:
        config.defrost()
        config.SYSTEM.RUN_RETENTION_DAYS = old_retention
        config.freeze()

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert not (runs_dir / run_bad.run_id).exists()


@pytest.mark.asyncio
async def test_cleanup_handles_missing_run_dir(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    run_missing = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    store.create_run(run_missing.run_id, cache_key="k1", status=RunStatus.FAILED)
    workspace_manager.delete_run_dir(run_missing.run_id)

    old_retention = config.SYSTEM.RUN_RETENTION_DAYS
    config.defrost()
    config.SYSTEM.RUN_RETENTION_DAYS = 1
    config.freeze()
    try:
        await manager.cleanup_expired_runs()
    finally:
        config.defrost()
        config.SYSTEM.RUN_RETENTION_DAYS = old_retention
        config.freeze()

    with store._connect() as conn:
        remaining = {row["run_id"] for row in conn.execute("SELECT run_id FROM runs")}
    assert run_missing.run_id not in remaining


@pytest.mark.asyncio
async def test_cleanup_disabled_when_retention_zero(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    run_old = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    store.create_run(run_old.run_id, cache_key="k1", status=RunStatus.SUCCEEDED)
    _set_run_row(store, run_old.run_id, RunStatus.SUCCEEDED, (datetime.utcnow() - timedelta(days=10)).isoformat())

    old_retention = config.SYSTEM.RUN_RETENTION_DAYS
    config.defrost()
    config.SYSTEM.RUN_RETENTION_DAYS = 0
    config.freeze()
    try:
        await manager.cleanup_expired_runs()
    finally:
        config.defrost()
        config.SYSTEM.RUN_RETENTION_DAYS = old_retention
        config.freeze()

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert (runs_dir / run_old.run_id).exists()
    with store._connect() as conn:
        remaining = {row["run_id"] for row in conn.execute("SELECT run_id FROM runs")}
    assert run_old.run_id in remaining


def test_clear_all_removes_runs_and_requests(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    manager = RunCleanupManager()

    run_response = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    store.create_run(run_response.run_id, cache_key="k1", status=RunStatus.SUCCEEDED)

    request_id = "request-clear"
    workspace_manager.create_request(request_id, {"skill_id": "s"})
    store.create_request(
        request_id=request_id,
        skill_id="s",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    counts = manager.clear_all()
    assert counts["runs"] >= 1
    assert counts["requests"] >= 1

    second_counts = manager.clear_all()
    assert second_counts["runs"] == 0
    assert second_counts["requests"] == 0
    assert second_counts["cache_entries"] == 0

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    requests_dir = Path(config.SYSTEM.REQUESTS_DIR)
    assert not any(runs_dir.iterdir())
    assert not any(requests_dir.iterdir())


@pytest.mark.asyncio
async def test_cleanup_stale_trust_entries_passes_active_run_dirs(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_store", store)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.workspace_manager", workspace_manager)

    run_response = workspace_manager.create_run(RunCreateRequest(skill_id="s", engine="gemini", parameter={}))
    store.create_run(run_response.run_id, cache_key="k1", status=RunStatus.RUNNING)

    class RecorderTrustManager:
        def __init__(self):
            self.active = None

        def cleanup_stale_entries(self, active_run_dirs):
            self.active = [str(path) for path in active_run_dirs]

    recorder = RecorderTrustManager()
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_folder_trust_manager", recorder)

    manager = RunCleanupManager()
    await manager.cleanup_stale_trust_entries()

    assert recorder.active is not None
    assert any(run_response.run_id in path for path in recorder.active)
