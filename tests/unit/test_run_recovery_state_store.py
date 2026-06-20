import pytest

from server.runtime.workspace_layout import require_layout_from_record
from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.orchestration.run_store_request_store import RunRegistryStore, RunRequestStore
from server.services.orchestration.run_store_state_store import RunRecoveryStateStore


@pytest.mark.asyncio
async def test_run_recovery_state_store_list_active_run_ids(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    run_store = RunRegistryStore(database)
    recovery_store = RunRecoveryStateStore(database)

    await run_store.create_run("run-q", "k1", "queued")
    await run_store.create_run("run-r", "k2", "running")
    await run_store.create_run("run-w", "k4", "waiting_user")
    await run_store.create_run("run-s", "k3", "succeeded")

    active = set(await recovery_store.list_active_run_ids())
    assert active == {"run-q", "run-r", "run-w"}


@pytest.mark.asyncio
async def test_run_recovery_state_store_cancel_requested_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    run_store = RunRegistryStore(database)
    recovery_store = RunRecoveryStateStore(database)

    await run_store.create_run("run-1", None, "queued")
    assert await recovery_store.is_cancel_requested("run-1") is False
    changed = await recovery_store.set_cancel_requested("run-1", True)
    assert changed is True
    assert await recovery_store.is_cancel_requested("run-1") is True


@pytest.mark.asyncio
async def test_run_recovery_state_store_roundtrip_incomplete_runs(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    request_store = RunRequestStore(database)
    run_store = RunRegistryStore(database)
    recovery_store = RunRecoveryStateStore(database)

    await request_store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    workspace_dir = tmp_path / "workspaces" / "run-1"
    await run_store.create_run(
        "run-1",
        None,
        "waiting_user",
        result_path=str(workspace_dir / "result" / "skill.1" / "result.json"),
        workspace_id="run-1",
        workspace_dir=str(workspace_dir),
        workspace_namespace="skill.1",
        input_manifest_path=str(workspace_dir / ".audit" / "skill.1" / "input_manifest.json"),
    )
    await request_store.update_request_run_id("req-1", "run-1")
    await recovery_store.set_recovery_info(
        "run-1",
        recovery_state="recovered_waiting",
        recovery_reason="resumable_waiting_preserved",
        recovered_at="2026-02-16T00:00:00",
    )

    rows = await recovery_store.list_incomplete_runs()
    assert len(rows) == 1
    assert rows[0]["run_status"] == "waiting_user"
    assert rows[0]["recovery_state"] == "recovered_waiting"
    layout = require_layout_from_record(rows[0])
    assert layout.workspace_id == "run-1"
    assert layout.workspace_dir == workspace_dir
    assert layout.namespace == "skill.1"
    assert rows[0]["result_path"] == str(workspace_dir / "result" / "skill.1" / "result.json")
    assert rows[0]["run_input_manifest_path"] == str(
        workspace_dir / ".audit" / "skill.1" / "input_manifest.json"
    )
