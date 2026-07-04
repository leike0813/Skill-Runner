import io
import json
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, UploadFile, HTTPException

from server.config import config
from server.models import RequestSkillSource, RunCreateRequest, RunStatus, SkillManifest
from server.routers import jobs as jobs_router
from server.services.orchestration.run_execution_core import validate_runtime_and_model_options
from server.services.platform.cache_key_builder import (
    build_input_manifest,
    compute_cache_key,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_skill_fingerprint,
    compute_skill_package_hash,
)
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.platform.runtime_env_options import runtime_env_secret_service
from server.services.platform.runtime_preamble_options import runtime_preamble_secret_service


def _normalized_engine_options(*, engine: str, model: str) -> dict[str, Any]:
    _runtime_options, engine_options = validate_runtime_and_model_options(
        engine=engine,
        model=model,
        runtime_options={},
    )
    return engine_options


@pytest.fixture(autouse=True)
def _allow_workspace_skill(monkeypatch, temp_config_dirs):
    skill = SkillManifest(
        id="demo-skill",
        name="demo-skill",
        engines=["codex"],
        path=temp_config_dirs
    )
    monkeypatch.setattr(
        "server.services.skill.skill_registry.skill_registry.get_skill",
        lambda skill_id: skill if skill_id == "demo-skill" else None
    )


def _create_skill(
    base_dir: Path,
    skill_id: str,
    with_input_schema: bool,
    engines: list[str] | None = None,
    unsupported_engines: list[str] | None = None,
    include_engines: bool = True,
    execution_modes: list[str] | None = None,
    runtime_default_options: dict[str, Any] | None = None,
) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("skill")
    if engines is None:
        engines = ["codex"]
    if unsupported_engines is None:
        unsupported_engines = []
    if execution_modes is None:
        execution_modes = ["auto", "interactive"]
    runner_payload = {
        "id": skill_id,
        "execution_modes": execution_modes,
    }
    if include_engines:
        runner_payload["engines"] = engines
    if unsupported_engines:
        runner_payload["unsupported_engines"] = unsupported_engines
    if runtime_default_options is not None:
        runner_payload["runtime"] = {"default_options": runtime_default_options}
    (assets_dir / "runner.json").write_text(
        json.dumps(runner_payload)
    )

    schemas = {}
    if with_input_schema:
        schema_path = assets_dir / "input.schema.json"
        schema_path.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "input.txt": {"type": "string"}
                    },
                    "required": ["input.txt"]
                }
            )
        )
        schemas["input"] = "assets/input.schema.json"

    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        schemas=schemas,
        engines=engines if include_engines else [],
        unsupported_engines=unsupported_engines,
        execution_modes=execution_modes,
        runtime={"default_options": runtime_default_options or {}},
    )


def _create_inline_input_skill(base_dir: Path, skill_id: str) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("skill")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "engines": ["codex"],
                "execution_modes": ["auto", "interactive"],
            }
        )
    )
    (assets_dir / "input.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "x-input-source": "inline"
                    }
                },
                "required": ["query"]
            }
        )
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        schemas={"input": "assets/input.schema.json"},
        engines=["codex"],
        execution_modes=["auto", "interactive"],
    )


def _create_file_binding_skill(
    base_dir: Path,
    skill_id: str,
    *,
    required_keys: list[str] | None = None,
) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("skill")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "engines": ["codex"],
                "execution_modes": ["auto", "interactive"],
            }
        )
    )
    if required_keys is None:
        required_keys = ["artifact_file"]
    (assets_dir / "input.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    key: {"type": "string", "x-input-source": "file"}
                    for key in required_keys
                },
                "required": required_keys,
            }
        )
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        schemas={"input": "assets/input.schema.json"},
        engines=["codex"],
        execution_modes=["auto", "interactive"],
    )


def _patch_skill_registry(monkeypatch: pytest.MonkeyPatch, skill: SkillManifest) -> None:
    def _get_skill(skill_id: str) -> SkillManifest | None:
        return skill if skill_id == skill.id else None

    monkeypatch.setattr(jobs_router.skill_registry, "get_skill", _get_skill)


def _patch_run_store(monkeypatch: pytest.MonkeyPatch, store: RunStore) -> None:
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr("server.runtime.observability.run_source_adapter.run_store", store)


def _manifest_hash_for_content(tmp_path: Path, filename: str, content: str) -> str:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / filename).write_text(content)
    manifest = build_input_manifest(uploads_dir)
    return compute_input_manifest_hash(manifest)


async def _create_cached_succeeded_run(
    store: RunStore,
    *,
    cache_key: str,
    skill_id: str = "demo-skill",
) -> dict[str, Any]:
    run_id = f"cached-{cache_key[:16]}"
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    namespace = f"{skill_id}.1"
    artifact_path = run_dir / "artifacts" / "output.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("ok", encoding="utf-8")
    result_path = run_dir / "result" / namespace / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "data": {"ok": True},
                "artifacts": ["artifacts/output.txt"],
            }
        ),
        encoding="utf-8",
    )
    input_manifest_path = run_dir / ".audit" / namespace / "input_manifest.json"
    input_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    input_manifest_path.write_text("{}", encoding="utf-8")
    await store.create_run(
        run_id,
        cache_key,
        RunStatus.SUCCEEDED,
        result_path=str(result_path),
        workspace_id=run_id,
        workspace_dir=str(run_dir),
        workspace_namespace=namespace,
        input_manifest_path=str(input_manifest_path),
        workspace_output_token=f"token-{run_id}",
    )
    await store.record_cache_entry(cache_key, run_id)
    return {
        "run_id": run_id,
        "workspace_dir": str(run_dir),
        "workspace_namespace": namespace,
        "result_path": str(result_path),
    }


async def _create_succeeded_workspace_request(
    store: RunStore,
    *,
    request_id: str,
    run_id: str,
    skill_id: str = "demo-skill",
    workspace_dir: Path | None = None,
    workspace_output_token: str | None = None,
) -> Path:
    if workspace_dir is None:
        workspace_dir = Path(config.SYSTEM.WORKSPACES_DIR) / run_id
    namespace = f"{skill_id}.1"
    result_path = workspace_dir / "result" / namespace / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"status":"success","data":{"ok":true}}', encoding="utf-8")
    await store.create_request(
        request_id=request_id,
        skill_id=skill_id,
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={},
        input_data={},
    )
    await store.create_run(
        run_id,
        None,
        RunStatus.SUCCEEDED,
        result_path=str(result_path),
        workspace_id=workspace_dir.name,
        workspace_dir=str(workspace_dir),
        workspace_namespace=namespace,
        workspace_output_token=workspace_output_token or f"token-{run_id}",
    )
    await store.bind_request_run_id(
        request_id,
        run_id,
        status=RunStatus.SUCCEEDED.value,
    )
    return workspace_dir


async def _assert_cached_request_routes(
    store: RunStore,
    *,
    request_id: str,
    cached_run: dict[str, Any],
) -> None:
    request_record = await store.get_request(request_id)
    assert request_record is not None
    assert request_record["run_id"] == cached_run["run_id"]
    assert request_record["workspace_dir"] == cached_run["workspace_dir"]
    assert request_record["workspace_namespace"] == cached_run["workspace_namespace"]
    assert request_record["result_path"] == cached_run["result_path"]

    state = await store.get_run_state(request_id)
    projection = await store.get_current_projection(request_id)
    assert state is not None
    assert projection is not None
    assert state["request_id"] == request_id
    assert projection["request_id"] == request_id
    assert state["run_id"] == cached_run["run_id"]
    assert projection["run_id"] == cached_run["run_id"]
    assert state["status"] == RunStatus.SUCCEEDED.value
    assert projection["status"] == RunStatus.SUCCEEDED.value

    result_response = await jobs_router.get_run_result(request_id)
    assert result_response.request_id == request_id
    assert result_response.result["data"] == {"ok": True}

    artifacts_response = await jobs_router.get_run_artifacts(request_id)
    assert artifacts_response.request_id == request_id
    assert artifacts_response.artifacts == ["artifacts/output.txt"]

    bundle_response = await jobs_router.get_run_bundle(request_id)
    assert str(bundle_response.path).endswith("run_bundle.zip")
    assert Path(bundle_response.path).exists()


class _RejectConcurrency:
    async def admit_or_reject(self) -> bool:
        return False


def _build_upload_zip(filename: str, content: str) -> UploadFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(filename, content)
    buffer.seek(0)
    file_obj = SpooledTemporaryFile()
    file_obj.write(buffer.getvalue())
    file_obj.seek(0)
    return UploadFile(filename="input.zip", file=file_obj)


def _build_skill_package_upload(
    *,
    skill_id: str = "temp-upload-skill",
    engine: str = "codex",
    runtime_default_options: dict[str, Any] | None = None,
) -> UploadFile:
    buffer = io.BytesIO()
    runner = {
        "id": skill_id,
        "engines": [engine],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
    }
    if runtime_default_options is not None:
        runner["runtime"] = {"default_options": runtime_default_options}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/output.schema.json", json.dumps({"type": "object", "properties": {}}))
    file_obj = SpooledTemporaryFile()
    file_obj.write(buffer.getvalue())
    file_obj.seek(0)
    return UploadFile(filename="skill_package.zip", file=file_obj)


def _create_temp_equivalent_installed_skill(
    base_dir: Path,
    *,
    skill_id: str = "temp-upload-skill",
    engine: str = "codex",
) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    runner = {
        "id": skill_id,
        "engines": [engine],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
    }
    (skill_dir / "SKILL.md").write_text(f"---\nname: {skill_id}\n---\n")
    (assets_dir / "runner.json").write_text(json.dumps(runner))
    (assets_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (assets_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        schemas=runner["schemas"],
        engines=[engine],
        execution_modes=["auto", "interactive"],
    )


@pytest.mark.asyncio
async def test_create_run_cache_hit_without_input(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    manifest_hash = compute_input_manifest_hash({"files": []})
    model_name = "gpt-5.4-mini"
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model=model_name),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    cached_run = await _create_cached_succeeded_run(store, cache_key=cache_key, skill_id=skill.id)

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model=model_name
        ),
        background_tasks
    )

    assert response.cache_hit is True
    assert response.status == RunStatus.SUCCEEDED
    assert background_tasks.tasks == []

    await _assert_cached_request_routes(
        store,
        request_id=response.request_id,
        cached_run=cached_run,
    )


@pytest.mark.asyncio
async def test_create_run_stale_cache_entry_falls_back_to_cache_miss(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    manifest_hash = compute_input_manifest_hash({"files": []})
    model_name = "gpt-5.4-mini"
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model=model_name),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    await store.record_cache_entry(cache_key, "missing-run")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model=model_name
        ),
        background_tasks
    )

    assert response.cache_hit is False
    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "missing-run"


@pytest.mark.asyncio
async def test_create_run_rejects_when_queue_full(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr(jobs_router, "concurrency_manager", _RejectConcurrency())

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                parameter={"a": 1},
                model="gpt-5.4-mini"
            ),
            BackgroundTasks()
        )

    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_create_run_cache_miss_without_input(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini"
        ),
        background_tasks
    )

    assert response.cache_hit is False
    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["cache_key"]

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"]
    assert request_record["workspace_dir"]
    assert Path(str(request_record["workspace_dir"])).exists()


@pytest.mark.asyncio
async def test_create_run_runtime_env_is_redacted_and_not_in_cache_key(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    first = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"env": {"FOO": "secret-a"}},
        ),
        BackgroundTasks(),
    )
    second = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"env": {"FOO": "secret-b"}},
        ),
        BackgroundTasks(),
    )

    first_record = await store.get_request(first.request_id)
    second_record = await store.get_request(second.request_id)
    assert first_record is not None
    assert second_record is not None
    assert first_record["cache_key"] == second_record["cache_key"]
    assert first_record["runtime_options"]["env"] == {"FOO": {"redacted": True}}
    assert first_record["effective_runtime_options"]["env"] == {"FOO": {"redacted": True}}
    assert runtime_env_secret_service.load(request_id=first.request_id) == {"FOO": "secret-a"}

    audit_path = Path(first_record["input_manifest_path"])
    audit_payload = audit_path.read_text(encoding="utf-8")
    record_payload = json.dumps(first_record, sort_keys=True)
    assert "secret-a" not in audit_payload
    assert "secret-a" not in record_payload


@pytest.mark.asyncio
async def test_create_run_preamble_prompt_is_redacted_and_changes_cache_key(
    monkeypatch,
    temp_config_dirs,
):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    first = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"preamble_prompt": "first client context"},
        ),
        BackgroundTasks(),
    )
    second = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"preamble_prompt": "second client context"},
        ),
        BackgroundTasks(),
    )

    first_record = await store.get_request(first.request_id)
    second_record = await store.get_request(second.request_id)
    assert first_record is not None
    assert second_record is not None
    assert first_record["cache_key"] != second_record["cache_key"]

    descriptor = first_record["effective_runtime_options"]["preamble_prompt"]
    assert descriptor["redacted"] is True
    assert descriptor["length"] == len("first client context")
    assert first_record["runtime_options"]["preamble_prompt"] == descriptor
    assert (
        runtime_preamble_secret_service.load(request_id=first.request_id)
        == "first client context"
    )

    audit_path = Path(first_record["input_manifest_path"])
    audit_payload = audit_path.read_text(encoding="utf-8")
    record_payload = json.dumps(first_record, sort_keys=True)
    assert "first client context" not in audit_payload
    assert "first client context" not in record_payload


@pytest.mark.asyncio
async def test_create_run_preamble_prompt_uses_skill_default_and_request_override(
    monkeypatch,
    temp_config_dirs,
):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        runtime_default_options={"preamble_prompt": "default client context"},
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    default_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    override_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"preamble_prompt": "request client context"},
        ),
        BackgroundTasks(),
    )

    default_record = await store.get_request(default_response.request_id)
    override_record = await store.get_request(override_response.request_id)
    assert default_record is not None
    assert override_record is not None
    assert (
        runtime_preamble_secret_service.load(request_id=default_response.request_id)
        == "default client context"
    )
    assert (
        runtime_preamble_secret_service.load(request_id=override_response.request_id)
        == "request client context"
    )
    assert default_record["effective_runtime_options"]["preamble_prompt"]["length"] == len(
        "default client context"
    )
    assert override_record["effective_runtime_options"]["preamble_prompt"]["length"] == len(
        "request client context"
    )
    assert default_record["cache_key"] != override_record["cache_key"]


@pytest.mark.asyncio
async def test_create_run_reuses_succeeded_request_workspace(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    source_workspace = Path(config.SYSTEM.RUNS_DIR) / "run-a"
    (source_workspace / "result" / "demo-skill.1").mkdir(parents=True, exist_ok=True)
    source_result = source_workspace / "result" / "demo-skill.1" / "result.json"
    source_result.write_text('{"status":"success","data":{"ok":true}}', encoding="utf-8")

    await store.create_request(
        request_id="req-a",
        skill_id=skill.id,
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={},
        input_data={},
    )
    await store.create_run(
        "run-a",
        "cache-a",
        RunStatus.SUCCEEDED,
        result_path=str(source_result),
        workspace_id="run-a",
        workspace_dir=str(source_workspace),
        workspace_namespace="demo-skill.1",
        workspace_output_token="token-a",
    )
    await store.update_request_run_id("req-a", "run-a")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"step": 2},
            model="gpt-5.4-mini",
            runtime_options={
                "no_cache": True,
                "workspace": {"mode": "reuse", "request_id": "req-a"},
            },
        ),
        background_tasks,
    )

    assert response.cache_hit is False
    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["workspace_id"] == "run-a"
    assert request_record["workspace_dir"] == str(source_workspace)
    assert request_record["workspace_namespace"] == "demo-skill.2"
    assert request_record["workspace_source_request_id"] == "req-a"
    assert request_record["workspace_input_token"] == "token-a"
    assert request_record["result_path"] == str(source_workspace / "result" / "demo-skill.2" / "result.json")
    assert (
        request_record["run_input_manifest_path"]
        == str(source_workspace / ".audit" / "demo-skill.2" / "input_manifest.json")
    )

    b_result_path = Path(str(request_record["result_path"]))
    b_result_path.parent.mkdir(parents=True, exist_ok=True)
    b_result_path.write_text('{"status":"success","data":{"ok":true}}', encoding="utf-8")
    await store.update_run_status(request_record["run_id"], RunStatus.SUCCEEDED, str(b_result_path))
    await store.update_run_workspace_metadata(
        request_record["run_id"],
        result_path=str(b_result_path),
        workspace_output_token="token-b",
    )

    c_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"step": 3},
            model="gpt-5.4-mini",
            runtime_options={
                "no_cache": True,
                "workspace": {"mode": "reuse", "request_id": response.request_id},
            },
        ),
        BackgroundTasks(),
    )
    c_record = await store.get_request(c_response.request_id)
    assert c_record is not None
    assert c_record["workspace_dir"] == str(source_workspace)
    assert c_record["workspace_namespace"] == "demo-skill.3"
    assert c_record["workspace_source_request_id"] == response.request_id
    assert c_record["workspace_input_token"] == "token-b"


@pytest.mark.asyncio
async def test_create_run_materializes_workspace_file_binding_without_upload(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_file_binding_skill(temp_config_dirs, "binding-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    workspace_dir = await _create_succeeded_workspace_request(
        store,
        request_id="source-req",
        run_id="source-run",
        skill_id=skill.id,
        workspace_output_token="token-source",
    )
    source_file = workspace_dir / "runtime" / "sequence-file-handoff-artifact.json"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text('{"from":"source"}', encoding="utf-8")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            input={"artifact_file": "inputs/artifact_file/sequence-file-handoff-artifact.json"},
            parameter={},
            model="gpt-5.4-mini",
            runtime_options={
                "no_cache": True,
                "workspace": {
                    "mode": "reuse",
                    "request_id": "source-req",
                    "file_bindings": [
                        {
                            "input_key": "artifact_file",
                            "source_request_id": "source-req",
                            "source_path": "runtime/sequence-file-handoff-artifact.json",
                            "target_path": "inputs/artifact_file/sequence-file-handoff-artifact.json",
                        }
                    ],
                },
            },
        ),
        background_tasks,
    )

    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1
    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["request_upload_mode"] == "uploaded"
    run_upload = (
        Path(str(request_record["workspace_dir"]))
        / "uploads"
        / "inputs/artifact_file/sequence-file-handoff-artifact.json"
    )
    assert run_upload.read_text(encoding="utf-8") == '{"from":"source"}'
    manifest = build_input_manifest(Path(str(request_record["workspace_dir"])) / "uploads")
    assert [item["path"] for item in manifest["files"]] == [
        "inputs/artifact_file/sequence-file-handoff-artifact.json"
    ]
    assert manifest["files"][0]["size"] == len('{"from":"source"}')


@pytest.mark.asyncio
async def test_workspace_file_binding_content_changes_cache_key(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_file_binding_skill(temp_config_dirs, "binding-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    workspace_dir = await _create_succeeded_workspace_request(
        store,
        request_id="anchor-req",
        run_id="anchor-run",
        skill_id=skill.id,
        workspace_output_token="stable-token",
    )
    await _create_succeeded_workspace_request(
        store,
        request_id="source-b-req",
        run_id="source-b-run",
        skill_id=skill.id,
        workspace_dir=workspace_dir,
        workspace_output_token="other-token",
    )
    source_a = workspace_dir / "runtime" / "a.json"
    source_b = workspace_dir / "runtime" / "b.json"
    source_a.parent.mkdir(parents=True, exist_ok=True)
    source_a.write_text("alpha", encoding="utf-8")
    source_b.write_text("bravo", encoding="utf-8")

    async def _create_with_source(source_request_id: str, source_path: str) -> dict[str, Any]:
        response = await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                input={"artifact_file": "inputs/artifact_file/file.json"},
                parameter={},
                model="gpt-5.4-mini",
                runtime_options={
                    "no_cache": True,
                    "workspace": {
                        "mode": "reuse",
                        "request_id": "anchor-req",
                        "file_bindings": [
                            {
                                "input_key": "artifact_file",
                                "source_request_id": source_request_id,
                                "source_path": source_path,
                                "target_path": "inputs/artifact_file/file.json",
                            }
                        ],
                    },
                },
            ),
            BackgroundTasks(),
        )
        record = await store.get_request(response.request_id)
        assert record is not None
        return record

    first = await _create_with_source("anchor-req", "runtime/a.json")
    second = await _create_with_source("source-b-req", "runtime/b.json")

    assert first["input_manifest_hash"] != second["input_manifest_hash"]
    assert first["cache_key"] != second["cache_key"]


@pytest.mark.asyncio
async def test_create_run_rejects_unsafe_workspace_file_binding(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_file_binding_skill(temp_config_dirs, "binding-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    await _create_succeeded_workspace_request(
        store,
        request_id="source-req",
        run_id="source-run",
        skill_id=skill.id,
    )

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                input={"artifact_file": "inputs/artifact_file/file.json"},
                parameter={},
                model="gpt-5.4-mini",
                runtime_options={
                    "workspace": {
                        "mode": "reuse",
                        "request_id": "source-req",
                        "file_bindings": [
                            {
                                "input_key": "artifact_file",
                                "source_request_id": "source-req",
                                "source_path": "../runtime/file.json",
                                "target_path": "inputs/artifact_file/file.json",
                            }
                        ],
                    },
                },
            ),
            BackgroundTasks(),
        )

    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_create_run_rejects_workspace_file_binding_from_other_workspace(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_file_binding_skill(temp_config_dirs, "binding-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    await _create_succeeded_workspace_request(
        store,
        request_id="reuse-req",
        run_id="reuse-run",
        skill_id=skill.id,
    )
    other_workspace = await _create_succeeded_workspace_request(
        store,
        request_id="other-req",
        run_id="other-run",
        skill_id=skill.id,
    )
    other_file = other_workspace / "runtime" / "file.json"
    other_file.parent.mkdir(parents=True, exist_ok=True)
    other_file.write_text("other", encoding="utf-8")

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                input={"artifact_file": "inputs/artifact_file/file.json"},
                parameter={},
                model="gpt-5.4-mini",
                runtime_options={
                    "workspace": {
                        "mode": "reuse",
                        "request_id": "reuse-req",
                        "file_bindings": [
                            {
                                "input_key": "artifact_file",
                                "source_request_id": "other-req",
                                "source_path": "runtime/file.json",
                                "target_path": "inputs/artifact_file/file.json",
                            }
                        ],
                    },
                },
            ),
            BackgroundTasks(),
        )

    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_upload_workspace_file_binding_overwrites_zip_target(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_file_binding_skill(
        temp_config_dirs,
        "binding-skill",
        required_keys=["artifact_file", "extra_file"],
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    workspace_dir = await _create_succeeded_workspace_request(
        store,
        request_id="source-req",
        run_id="source-run",
        skill_id=skill.id,
    )
    source_file = workspace_dir / "runtime" / "artifact.json"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("bound-content", encoding="utf-8")

    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            input={
                "artifact_file": "inputs/artifact_file/file.json",
                "extra_file": "inputs/extra_file/file.txt",
            },
            parameter={},
            model="gpt-5.4-mini",
            runtime_options={
                "no_cache": True,
                "workspace": {
                    "mode": "reuse",
                    "request_id": "source-req",
                    "file_bindings": [
                        {
                            "input_key": "artifact_file",
                            "source_request_id": "source-req",
                            "source_path": "runtime/artifact.json",
                            "target_path": "inputs/artifact_file/file.json",
                        }
                    ],
                },
            },
        ),
        BackgroundTasks(),
    )
    assert create_response.status is None

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("inputs/artifact_file/file.json", "zip-content")
        zf.writestr("inputs/extra_file/file.txt", "extra-content")
    buffer.seek(0)
    file_obj = SpooledTemporaryFile()
    file_obj.write(buffer.getvalue())
    file_obj.seek(0)
    upload = UploadFile(filename="input.zip", file=file_obj)

    upload_response = await jobs_router.upload_file(
        create_response.request_id,
        background_tasks=BackgroundTasks(),
        file=upload,
    )

    assert upload_response.status == RunStatus.QUEUED
    request_record = await store.get_request(create_response.request_id)
    assert request_record is not None
    uploads_dir = Path(str(request_record["workspace_dir"])) / "uploads"
    assert (uploads_dir / "inputs/artifact_file/file.json").read_text(encoding="utf-8") == "bound-content"
    assert (uploads_dir / "inputs/extra_file/file.txt").read_text(encoding="utf-8") == "extra-content"


@pytest.mark.asyncio
async def test_create_run_applies_skill_runtime_default_options(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        runtime_default_options={"hard_timeout_seconds": 45},
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={},
        ),
        background_tasks,
    )
    assert response.cache_hit is False
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.kwargs["options"]["hard_timeout_seconds"] == 45

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert "hard_timeout_seconds" not in request_record["runtime_options"]
    assert request_record["effective_runtime_options"]["hard_timeout_seconds"] == 45


@pytest.mark.asyncio
async def test_create_run_request_runtime_options_override_skill_defaults(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        runtime_default_options={"hard_timeout_seconds": 45},
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"hard_timeout_seconds": 9},
        ),
        background_tasks,
    )
    assert response.cache_hit is False
    task = background_tasks.tasks[0]
    assert task.kwargs["options"]["hard_timeout_seconds"] == 9

    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["runtime_options"]["hard_timeout_seconds"] == 9
    assert request_record["effective_runtime_options"]["hard_timeout_seconds"] == 9


@pytest.mark.asyncio
async def test_create_run_invalid_skill_runtime_defaults_emit_warning_payload(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        runtime_default_options={"unknown_key": 1},
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={},
        ),
        background_tasks,
    )
    assert response.cache_hit is False
    task = background_tasks.tasks[0]
    warning_payloads = task.kwargs["options"]["__runtime_option_warnings"]
    assert isinstance(warning_payloads, list)
    assert warning_payloads
    assert warning_payloads[0]["code"] == "SKILL_RUNTIME_DEFAULT_OPTION_IGNORED"


@pytest.mark.asyncio
async def test_create_run_with_input_schema_requires_upload(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=True)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini"
        ),
        background_tasks
    )

    assert response.cache_hit is False
    assert response.status is None
    assert background_tasks.tasks == []


@pytest.mark.asyncio
async def test_create_run_with_inline_only_input_starts_immediately(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_inline_input_skill(temp_config_dirs, "demo-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            input={"query": "hello"},
            parameter={},
            model="gpt-5.4-mini",
        ),
        background_tasks
    )

    assert response.cache_hit is False
    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_create_run_with_inline_required_missing_returns_400(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_inline_input_skill(temp_config_dirs, "demo-skill")
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                input={},
                parameter={},
                model="gpt-5.4-mini",
            ),
            BackgroundTasks()
        )

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_create_run_allows_missing_engines_and_defaults_to_all(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        include_engines=False,
    )
    _patch_skill_registry(monkeypatch, skill)

    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    assert response.request_id


@pytest.mark.asyncio
async def test_create_run_rejects_engine_not_allowed(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False, engines=["opencode"])
    _patch_skill_registry(monkeypatch, skill)

    background_tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                parameter={"a": 1}
            ),
            background_tasks
        )

    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "SKILL_ENGINE_UNSUPPORTED"
    assert detail["requested_engine"] == "codex"


@pytest.mark.asyncio
async def test_create_run_rejects_engine_denied_by_unsupported_engines(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        include_engines=False,
        unsupported_engines=["codex"],
    )
    _patch_skill_registry(monkeypatch, skill)

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                parameter={"a": 1}
            ),
            BackgroundTasks()
        )

    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "SKILL_ENGINE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_upload_file_cache_hit(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=True)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini"
        ),
        background_tasks
    )

    manifest_hash = _manifest_hash_for_content(temp_config_dirs, "input.txt", "hello")
    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model="gpt-5.4-mini"),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    cached_run = await _create_cached_succeeded_run(store, cache_key=cache_key, skill_id=skill.id)

    upload = _build_upload_zip("input.txt", "hello")

    upload_response = await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=BackgroundTasks(),
        file=upload,
    )

    assert upload_response.cache_hit is True
    assert "input.txt" in upload_response.extracted_files

    await _assert_cached_request_routes(
        store,
        request_id=create_response.request_id,
        cached_run=cached_run,
    )


@pytest.mark.asyncio
async def test_upload_file_interactive_skips_cache_hit(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=True)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"execution_mode": "interactive"}
        ),
        background_tasks
    )

    manifest_hash = _manifest_hash_for_content(temp_config_dirs, "input.txt", "hello")
    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model="gpt-5.4-mini"),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    await store.record_cache_entry(cache_key, "run-cached")

    upload = _build_upload_zip("input.txt", "hello")
    upload_response = await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=BackgroundTasks(),
        file=upload,
    )

    assert upload_response.cache_hit is False
    request_record = await store.get_request(create_response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"


@pytest.mark.asyncio
async def test_upload_file_cache_miss(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=True)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    background_tasks = BackgroundTasks()
    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini"
        ),
        background_tasks
    )

    upload = _build_upload_zip("input.txt", "hello")

    upload_tasks = BackgroundTasks()
    upload_response = await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=upload_tasks,
        file=upload,
    )

    assert upload_response.cache_hit is False
    assert len(upload_tasks.tasks) == 1
    request_record = await store.get_request(create_response.request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id
    run_dir = Path(str(request_record["workspace_dir"]))
    assert (run_dir / "uploads" / "input.txt").exists()

    request_dir = Path(config.SYSTEM.REQUESTS_DIR) / create_response.request_id
    assert not (request_dir / "uploads").exists()


@pytest.mark.asyncio
async def test_upload_file_rejects_when_queue_full(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)
    monkeypatch.setattr(jobs_router, "concurrency_manager", _RejectConcurrency())

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=True)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini"
        ),
        BackgroundTasks()
    )

    upload = _build_upload_zip("input.txt", "hello")

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.upload_file(
            request_id=create_response.request_id,
            background_tasks=BackgroundTasks(),
            file=upload,
        )

    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_upload_temp_skill_creates_run_without_installed_registry_lookup(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        jobs_router.skill_registry,
        "get_skill",
        lambda _skill_id: (_ for _ in ()).throw(AssertionError("installed registry lookup should not happen")),
    )

    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_source=RequestSkillSource.TEMP_UPLOAD,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"no_cache": True},
        ),
        BackgroundTasks(),
    )
    assert create_response.status is None

    upload_tasks = BackgroundTasks()
    upload_response = await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=upload_tasks,
        file=None,
        skill_package=_build_skill_package_upload(skill_id="temp-upload-skill", engine="codex"),
    )

    assert upload_response.cache_hit is False
    assert len(upload_tasks.tasks) == 1
    request_record = await store.get_request(create_response.request_id)
    assert request_record is not None
    assert request_record["skill_source"] == "temp_upload"
    assert request_record["skill_id"] == "temp-upload-skill"
    assert request_record["run_id"]
    run_dir = Path(str(request_record["workspace_dir"]))
    assert run_dir.exists()


@pytest.mark.asyncio
async def test_upload_temp_skill_applies_runtime_default_options(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )

    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_source=RequestSkillSource.TEMP_UPLOAD,
            engine="codex",
            parameter={},
            model="gpt-5.4-mini",
            runtime_options={},
        ),
        BackgroundTasks(),
    )
    assert create_response.status is None

    upload_tasks = BackgroundTasks()
    await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=upload_tasks,
        file=None,
        skill_package=_build_skill_package_upload(
            skill_id="temp-upload-skill",
            engine="codex",
            runtime_default_options={"hard_timeout_seconds": 66},
        ),
    )

    request_record = await store.get_request(create_response.request_id)
    assert request_record is not None
    assert "hard_timeout_seconds" not in request_record["runtime_options"]
    assert request_record["effective_runtime_options"]["hard_timeout_seconds"] == 66
    task = upload_tasks.tasks[0]
    assert task.kwargs["options"]["hard_timeout_seconds"] == 66


@pytest.mark.asyncio
async def test_upload_temp_skill_different_inline_input_does_not_hit_cache(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )

    first = await jobs_router.create_run(
        RunCreateRequest(
            skill_source=RequestSkillSource.TEMP_UPLOAD,
            engine="codex",
            input={"query": "one"},
            parameter={"a": 1},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    await jobs_router.upload_file(
        request_id=first.request_id,
        background_tasks=BackgroundTasks(),
        file=None,
        skill_package=_build_skill_package_upload(skill_id="temp-upload-skill", engine="codex"),
    )
    first_record = await store.get_request(first.request_id)
    assert first_record is not None
    await store.record_cache_entry(first_record["cache_key"], "run-cached-first")

    second = await jobs_router.create_run(
        RunCreateRequest(
            skill_source=RequestSkillSource.TEMP_UPLOAD,
            engine="codex",
            input={"query": "two"},
            parameter={"a": 1},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    second_response = await jobs_router.upload_file(
        request_id=second.request_id,
        background_tasks=BackgroundTasks(),
        file=None,
        skill_package=_build_skill_package_upload(skill_id="temp-upload-skill", engine="codex"),
    )
    second_record = await store.get_request(second.request_id)

    assert second_response.cache_hit is False
    assert second_record is not None
    assert second_record["cache_key"] != first_record["cache_key"]
    assert second_record["run_id"] != "run-cached-first"


@pytest.mark.asyncio
async def test_upload_temp_skill_can_hit_installed_cache_with_same_package_hash(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model},
    )

    installed_skill = _create_temp_equivalent_installed_skill(temp_config_dirs)
    package_hash = compute_skill_package_hash(installed_skill.path)
    manifest_hash = compute_input_manifest_hash({"files": []})
    cache_key = compute_cache_key(
        skill_id=installed_skill.id,
        engine="codex",
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model="gpt-5.4-mini"),
        input_manifest_hash=manifest_hash,
        inline_input_hash=compute_inline_input_hash({"query": "same"}),
        skill_package_hash=package_hash,
    )
    cached_run = await _create_cached_succeeded_run(
        store,
        cache_key=cache_key,
        skill_id=installed_skill.id,
    )

    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_source=RequestSkillSource.TEMP_UPLOAD,
            engine="codex",
            input={"query": "same"},
            parameter={"a": 1},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    upload_response = await jobs_router.upload_file(
        request_id=create_response.request_id,
        background_tasks=BackgroundTasks(),
        file=None,
        skill_package=_build_skill_package_upload(skill_id=installed_skill.id, engine="codex"),
    )
    request_record = await store.get_request(create_response.request_id)

    assert upload_response.cache_hit is True
    assert request_record is not None
    assert request_record["run_id"] == cached_run["run_id"]
    state = await store.get_run_state(create_response.request_id)
    assert state is not None
    assert state["status"] == RunStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_create_run_no_cache_skips_hit(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    manifest_hash = compute_input_manifest_hash({"files": []})
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model="gpt-5.4-mini"),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    await store.record_cache_entry(cache_key, "run-cached")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"no_cache": True}
        ),
        background_tasks
    )

    assert response.cache_hit is False
    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"
    run_record = await store.get_run(request_record["run_id"])
    assert run_record is not None
    assert run_record["cache_key"] is None


@pytest.mark.asyncio
async def test_create_run_interactive_skips_cache_hit(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill_fp = compute_skill_fingerprint(skill, "codex")
    skill_package_hash = compute_skill_package_hash(skill.path)
    manifest_hash = compute_input_manifest_hash({"files": []})
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="codex",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options=_normalized_engine_options(engine="codex", model="gpt-5.4-mini"),
        input_manifest_hash=manifest_hash,
        skill_package_hash=skill_package_hash,
    )
    await store.record_cache_entry(cache_key, "run-cached")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={"a": 1},
            model="gpt-5.4-mini",
            runtime_options={"execution_mode": "interactive"}
        ),
        background_tasks
    )

    assert response.cache_hit is False
    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"
    run_record = await store.get_run(request_record["run_id"])
    assert run_record is not None
    assert run_record["cache_key"] is None


@pytest.mark.asyncio
async def test_create_run_rejects_interactive_when_skill_declares_auto_only(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        execution_modes=["auto"],
    )
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="codex",
                parameter={"a": 1},
                model="gpt-5.4-mini",
                runtime_options={"execution_mode": "interactive"},
            ),
            BackgroundTasks(),
        )

    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "SKILL_EXECUTION_MODE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_get_run_artifacts_lists_outputs(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    request_id = "request-artifacts"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="codex", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(str(run_response.workspace_dir))
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")
    result_path = run_dir / "result" / "demo-skill.1" / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        '{"status":"success","artifacts":["artifacts/output.txt"]}'
    )

    await store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    await store.create_run(
        run_response.run_id,
        cache_key=None,
        status=RunStatus.SUCCEEDED,
        result_path=str(result_path),
        workspace_id=run_response.run_id,
        workspace_dir=str(run_dir),
        workspace_namespace="demo-skill.1",
    )
    await store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_artifacts(request_id)
    assert response.request_id == request_id
    assert "artifacts/output.txt" in response.artifacts


@pytest.mark.asyncio
async def test_get_run_artifacts_empty(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    request_id = "request-empty-artifacts"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="codex", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(str(run_response.workspace_dir))

    await store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    await store.create_run(
        run_response.run_id,
        cache_key=None,
        status=RunStatus.SUCCEEDED,
        workspace_id=run_response.run_id,
        workspace_dir=str(run_dir),
        workspace_namespace="demo-skill.1",
    )
    await store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_artifacts(request_id)
    assert response.request_id == request_id
    assert response.artifacts == []


@pytest.mark.asyncio
async def test_get_run_bundle_returns_zip(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    request_id = "request-bundle"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="codex", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(str(run_response.workspace_dir))
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")
    result_path = run_dir / "result" / "demo-skill.1" / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        '{"status":"success","artifacts":["artifacts/output.txt"]}'
    )

    await store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    await store.create_run(
        run_response.run_id,
        cache_key=None,
        status=RunStatus.SUCCEEDED,
        result_path=str(result_path),
        workspace_id=run_response.run_id,
        workspace_dir=str(run_dir),
        workspace_namespace="demo-skill.1",
    )
    await store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_bundle(request_id)
    assert str(response.path).endswith("run_bundle.zip")
    assert Path(response.path).exists()


@pytest.mark.asyncio
async def test_get_run_artifacts_does_not_scan_unlisted_files(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    _patch_run_store(monkeypatch, store)

    request_id = "request-unlisted-artifacts"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="codex", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(str(run_response.workspace_dir))
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")
    result_path = run_dir / "result" / "demo-skill.1" / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"status":"success","artifacts":[]}')

    await store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    await store.create_run(
        run_response.run_id,
        cache_key=None,
        status=RunStatus.SUCCEEDED,
        result_path=str(result_path),
        workspace_id=run_response.run_id,
        workspace_dir=str(run_dir),
        workspace_namespace="demo-skill.1",
    )
    await store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_artifacts(request_id)
    assert response.artifacts == []
