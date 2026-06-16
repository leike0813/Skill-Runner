import pytest

from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.orchestration.run_store_request_store import RunRegistryStore, RunRequestStore


@pytest.mark.asyncio
async def test_run_request_store_roundtrip_create_and_get_request(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    request_store = RunRequestStore(database)

    await request_store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={"a": 1},
        engine_options={"model": "x"},
        runtime_options={"execution_mode": "interactive"},
        input_data={"foo": "bar"},
    )

    request = await request_store.get_request("req-1")
    assert request is not None
    assert request["parameter"]["a"] == 1
    assert request["input"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_run_request_store_get_request_by_run_id(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    request_store = RunRequestStore(database)
    run_store = RunRegistryStore(database)

    await request_store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={},
        input_data={"foo": "bar"},
    )
    await run_store.create_run(
        "run-1",
        None,
        "queued",
        result_path="/tmp/workspace/result/skill.2/result.json",
        workspace_id="workspace-1",
        workspace_dir="/tmp/workspace",
        workspace_namespace="skill.2",
        workspace_source_request_id="req-0",
        input_manifest_path="/tmp/workspace/.audit/skill.2/input_manifest.json",
        workspace_input_token="input-token",
        workspace_output_token="output-token",
    )
    await request_store.update_request_run_id("req-1", "run-1")

    request = await request_store.get_request_by_run_id("run-1")
    assert request is not None
    assert request["request_id"] == "req-1"
    assert request["input"]["foo"] == "bar"
    assert request["result_path"] == "/tmp/workspace/result/skill.2/result.json"
    assert request["workspace_id"] == "workspace-1"
    assert request["workspace_dir"] == "/tmp/workspace"
    assert request["workspace_namespace"] == "skill.2"
    assert request["workspace_source_request_id"] == "req-0"
    assert request["run_input_manifest_path"] == "/tmp/workspace/.audit/skill.2/input_manifest.json"
    assert request["workspace_input_token"] == "input-token"
    assert request["workspace_output_token"] == "output-token"


@pytest.mark.asyncio
async def test_run_request_store_lists_requests_with_runs_page(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    request_store = RunRequestStore(database)
    run_store = RunRegistryStore(database)

    for idx in range(3):
        request_id = f"req-{idx}"
        run_id = f"run-{idx}"
        await request_store.create_request(
            request_id=request_id,
            skill_id="skill",
            engine="gemini",
            parameter={},
            engine_options={},
            runtime_options={},
        )
        await run_store.create_run(run_id, None, "queued")
        await request_store.bind_request_run_id(request_id, run_id)

    rows = await request_store.list_requests_with_runs_page(page=1, page_size=2)
    assert len(rows) == 2
    assert all(row["run_id"] for row in rows)
