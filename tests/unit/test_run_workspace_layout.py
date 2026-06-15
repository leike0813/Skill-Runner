import pytest

from server.models import RunStatus
from server.services.orchestration.run_state_service import run_state_service
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.run_workspace_layout import layout_from_record


def test_layout_from_record_keeps_legacy_records_on_legacy_paths(tmp_path):
    record = {
        "run_id": "run-legacy",
        "skill_id": "legacy skill",
    }

    assert layout_from_record(record, tmp_path / "run-legacy") is None


def test_layout_from_record_uses_persisted_workspace_metadata(tmp_path):
    workspace = tmp_path / "workspace"
    record = {
        "run_id": "run-b",
        "skill_id": "skill/b",
        "workspace_id": "workspace-a",
        "workspace_dir": str(workspace),
        "workspace_namespace": "skill-b.2",
    }

    layout = layout_from_record(record, tmp_path / "run-b")

    assert layout is not None
    assert layout.workspace_id == "workspace-a"
    assert layout.workspace_dir == workspace
    assert layout.result_path == workspace / "result" / "skill-b.2" / "result.json"
    assert layout.input_manifest_path == workspace / ".audit" / "skill-b.2" / "input_manifest.json"


@pytest.mark.asyncio
async def test_run_store_projects_workspace_metadata_into_request(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_request(
        request_id="req-b",
        skill_id="skill-b",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"workspace": {"mode": "reuse", "request_id": "req-a"}},
        input_data={},
    )
    await store.create_run(
        "run-b",
        "cache-b",
        RunStatus.QUEUED,
        result_path="/workspace/result/skill-b.1/result.json",
        workspace_id="workspace-a",
        workspace_dir="/workspace",
        workspace_namespace="skill-b.1",
        workspace_source_request_id="req-a",
        input_manifest_path="/workspace/.audit/skill-b.1/input_manifest.json",
        workspace_input_token="token-a",
        workspace_output_token="token-b",
    )
    await store.update_request_run_id("req-b", "run-b")

    request = await store.get_request("req-b")

    assert request is not None
    assert request["workspace_id"] == "workspace-a"
    assert request["workspace_dir"] == "/workspace"
    assert request["workspace_namespace"] == "skill-b.1"
    assert request["workspace_source_request_id"] == "req-a"
    assert request["run_input_manifest_path"] == "/workspace/.audit/skill-b.1/input_manifest.json"
    assert request["workspace_input_token"] == "token-a"
    assert request["workspace_output_token"] == "token-b"


@pytest.mark.asyncio
async def test_run_state_service_writes_namespaced_state_when_layout_exists(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request_record = {
        "request_id": "req-b",
        "run_id": "run-b",
        "skill_id": "skill-b",
        "workspace_id": "workspace-a",
        "workspace_dir": str(workspace),
        "workspace_namespace": "skill-b.1",
        "runtime_options": {},
        "effective_runtime_options": {},
    }
    await store.create_run(
        "run-b",
        "cache-b",
        RunStatus.QUEUED,
        workspace_id="workspace-a",
        workspace_dir=str(workspace),
        workspace_namespace="skill-b.1",
    )

    await run_state_service.initialize_queued_state(
        run_dir=workspace,
        request_id="req-b",
        run_id="run-b",
        request_record=request_record,
        run_store_backend=store,
    )

    assert (workspace / ".state" / "skill-b.1" / "state.json").exists()
    assert (workspace / ".state" / "skill-b.1" / "dispatch.json").exists()
    assert not (workspace / ".state" / "state.json").exists()
    assert not (workspace / ".state" / "dispatch.json").exists()
