import io
import json
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, UploadFile, HTTPException

from server.config import config
from server.models import RunCreateRequest, RunStatus, SkillManifest
from server.routers import jobs as jobs_router
from server.services.cache_key_builder import (
    build_input_manifest,
    compute_cache_key,
    compute_input_manifest_hash,
    compute_skill_fingerprint
)
from server.services.run_store import RunStore
from server.services.workspace_manager import workspace_manager


@pytest.fixture(autouse=True)
def _allow_workspace_skill(monkeypatch, temp_config_dirs):
    skill = SkillManifest(
        id="demo-skill",
        name="demo-skill",
        engines=["gemini"],
        path=temp_config_dirs
    )
    monkeypatch.setattr(
        "server.services.skill_registry.skill_registry.get_skill",
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
) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("skill")
    if engines is None:
        engines = ["gemini"]
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
                "engines": ["gemini"],
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
        engines=["gemini"],
        execution_modes=["auto", "interactive"],
    )


def _patch_skill_registry(monkeypatch: pytest.MonkeyPatch, skill: SkillManifest) -> None:
    def _get_skill(skill_id: str) -> SkillManifest | None:
        return skill if skill_id == skill.id else None

    monkeypatch.setattr(jobs_router.skill_registry, "get_skill", _get_skill)


def _manifest_hash_for_content(tmp_path: Path, filename: str, content: str) -> str:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / filename).write_text(content)
    manifest = build_input_manifest(uploads_dir)
    return compute_input_manifest_hash(manifest)


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


@pytest.mark.asyncio
async def test_create_run_cache_hit_without_input(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False)
    _patch_skill_registry(monkeypatch, skill)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda engine, model: {"model": model}
    )

    skill_fp = compute_skill_fingerprint(skill, "gemini")
    manifest_hash = compute_input_manifest_hash({"files": []})
    model_name = "gemini-2.5-pro"
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": model_name},
        input_manifest_hash=manifest_hash
    )
    store.record_cache_entry(cache_key, "run-cached")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="gemini",
            parameter={"a": 1},
            model=model_name
        ),
        background_tasks
    )

    assert response.cache_hit is True
    assert response.status == RunStatus.SUCCEEDED
    assert background_tasks.tasks == []

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert not runs_dir.exists() or not any(runs_dir.iterdir())

    request_record = store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] == "run-cached"


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
                engine="gemini",
                parameter={"a": 1},
                model="gemini-2.5-pro"
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
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro"
        ),
        background_tasks
    )

    assert response.cache_hit is False
    assert response.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1

    request_record = store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["cache_key"]

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert runs_dir.exists()

    request_record = store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"]


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
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro"
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
            engine="gemini",
            input={"query": "hello"},
            parameter={},
            model="gemini-2.5-pro",
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
                engine="gemini",
                input={},
                parameter={},
                model="gemini-2.5-pro",
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
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro",
        ),
        BackgroundTasks(),
    )
    assert response.request_id


@pytest.mark.asyncio
async def test_create_run_rejects_engine_not_allowed(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(temp_config_dirs, "demo-skill", with_input_schema=False, engines=["codex"])
    _patch_skill_registry(monkeypatch, skill)

    background_tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="gemini",
                parameter={"a": 1}
            ),
            background_tasks
        )

    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "SKILL_ENGINE_UNSUPPORTED"
    assert detail["requested_engine"] == "gemini"


@pytest.mark.asyncio
async def test_create_run_rejects_engine_denied_by_unsupported_engines(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    skill = _create_skill(
        temp_config_dirs,
        "demo-skill",
        with_input_schema=False,
        include_engines=False,
        unsupported_engines=["gemini"],
    )
    _patch_skill_registry(monkeypatch, skill)

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.create_run(
            RunCreateRequest(
                skill_id=skill.id,
                engine="gemini",
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
    monkeypatch.setattr(jobs_router, "run_store", store)

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
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro"
        ),
        background_tasks
    )

    manifest_hash = _manifest_hash_for_content(temp_config_dirs, "input.txt", "hello")
    skill_fp = compute_skill_fingerprint(skill, "gemini")
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "gemini-2.5-pro"},
        input_manifest_hash=manifest_hash
    )
    store.record_cache_entry(cache_key, "run-cached")

    upload = _build_upload_zip("input.txt", "hello")

    upload_response = await jobs_router.upload_file(
        create_response.request_id,
        upload,
        BackgroundTasks()
    )

    assert upload_response.cache_hit is True
    assert "input.txt" in upload_response.extracted_files

    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    assert not runs_dir.exists() or not any(runs_dir.iterdir())

    request_record = store.get_request(create_response.request_id)
    assert request_record is not None
    assert request_record["run_id"] == "run-cached"


@pytest.mark.asyncio
async def test_upload_file_interactive_skips_cache_hit(monkeypatch, temp_config_dirs):
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
    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro",
            runtime_options={"execution_mode": "interactive"}
        ),
        background_tasks
    )

    manifest_hash = _manifest_hash_for_content(temp_config_dirs, "input.txt", "hello")
    skill_fp = compute_skill_fingerprint(skill, "gemini")
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "gemini-2.5-pro"},
        input_manifest_hash=manifest_hash
    )
    store.record_cache_entry(cache_key, "run-cached")

    upload = _build_upload_zip("input.txt", "hello")
    upload_response = await jobs_router.upload_file(
        create_response.request_id,
        upload,
        BackgroundTasks()
    )

    assert upload_response.cache_hit is False
    request_record = store.get_request(create_response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"


@pytest.mark.asyncio
async def test_upload_file_cache_miss(monkeypatch, temp_config_dirs):
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
    create_response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro"
        ),
        background_tasks
    )

    upload = _build_upload_zip("input.txt", "hello")

    upload_tasks = BackgroundTasks()
    upload_response = await jobs_router.upload_file(
        create_response.request_id,
        upload,
        upload_tasks
    )

    assert upload_response.cache_hit is False
    assert len(upload_tasks.tasks) == 1
    request_record = store.get_request(create_response.request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    runs_dir = Path(config.SYSTEM.RUNS_DIR)
    run_dir = runs_dir / run_id
    assert (run_dir / "uploads" / "input.txt").exists()

    request_dir = Path(config.SYSTEM.REQUESTS_DIR) / create_response.request_id
    assert not (request_dir / "uploads").exists()


@pytest.mark.asyncio
async def test_upload_file_rejects_when_queue_full(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
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
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro"
        ),
        BackgroundTasks()
    )

    upload = _build_upload_zip("input.txt", "hello")

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.upload_file(
            create_response.request_id,
            upload,
            BackgroundTasks()
        )

    assert excinfo.value.status_code == 429


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

    skill_fp = compute_skill_fingerprint(skill, "gemini")
    manifest_hash = compute_input_manifest_hash({"files": []})
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "gemini-2.5-pro"},
        input_manifest_hash=manifest_hash
    )
    store.record_cache_entry(cache_key, "run-cached")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro",
            runtime_options={"no_cache": True}
        ),
        background_tasks
    )

    assert response.cache_hit is False
    request_record = store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"


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

    skill_fp = compute_skill_fingerprint(skill, "gemini")
    manifest_hash = compute_input_manifest_hash({"files": []})
    cache_key = compute_cache_key(
        skill_id=skill.id,
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "gemini-2.5-pro"},
        input_manifest_hash=manifest_hash
    )
    store.record_cache_entry(cache_key, "run-cached")

    background_tasks = BackgroundTasks()
    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="gemini",
            parameter={"a": 1},
            model="gemini-2.5-pro",
            runtime_options={"execution_mode": "interactive"}
        ),
        background_tasks
    )

    assert response.cache_hit is False
    request_record = store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["run_id"] != "run-cached"


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
                engine="gemini",
                parameter={"a": 1},
                model="gemini-2.5-pro",
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
    monkeypatch.setattr(jobs_router, "run_store", store)

    request_id = "request-artifacts"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="gemini", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_response.run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")

    store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_artifacts(request_id)
    assert response.request_id == request_id
    assert "artifacts/output.txt" in response.artifacts


@pytest.mark.asyncio
async def test_get_run_artifacts_empty(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    request_id = "request-empty-artifacts"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="gemini", parameter={})
    run_response = workspace_manager.create_run(run_request)

    store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_artifacts(request_id)
    assert response.request_id == request_id
    assert response.artifacts == []


@pytest.mark.asyncio
async def test_get_run_bundle_returns_zip(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    request_id = "request-bundle"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="gemini", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_response.run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")
    (run_dir / "result" / "result.json").write_text('{"status":"success"}')

    store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={"debug": True}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.get_run_bundle(request_id)
    assert str(response.path).endswith("run_bundle_debug.zip")
    assert Path(response.path).exists()


@pytest.mark.asyncio
async def test_download_run_artifact_rejects_invalid_path(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    request_id = "request-invalid-path"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="gemini", parameter={})
    run_response = workspace_manager.create_run(run_request)

    store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    with pytest.raises(HTTPException) as exc:
        await jobs_router.download_run_artifact(request_id, "bundle/run_bundle.zip")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_download_run_artifact_success(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)

    request_id = "request-download-artifact"
    run_request = RunCreateRequest(skill_id="demo-skill", engine="gemini", parameter={})
    run_response = workspace_manager.create_run(run_request)
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_response.run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "output.txt").write_text("ok")

    store.create_request(
        request_id=request_id,
        skill_id="demo-skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={}
    )
    store.update_request_run_id(request_id, run_response.run_id)

    response = await jobs_router.download_run_artifact(request_id, "artifacts/output.txt")
    assert Path(response.path).exists()
