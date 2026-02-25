import io
import json
import zipfile
from pathlib import Path

import pytest

from server.config import config
from server.models import RunStatus
from server.services.temp_skill_run_manager import TempSkillRunManager
from server.services.temp_skill_run_store import TempSkillRunStore


def _build_skill_zip(
    skill_id: str = "demo-temp-skill",
    *,
    include_engines: bool = True,
    unsupported_engines: list[str] | None = None,
) -> bytes:
    runner: dict[str, object] = {
        "id": skill_id,
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": [{"role": "result", "pattern": "out.txt", "required": True}],
    }
    if include_engines:
        runner["engines"] = ["gemini"]
    if unsupported_engines:
        runner["unsupported_engines"] = unsupported_engines
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/output.schema.json", json.dumps({"type": "object", "properties": {}}))
    return bio.getvalue()


def test_stage_and_cleanup_temp_skill(monkeypatch, temp_config_dirs):
    store = TempSkillRunStore(db_path=Path(config.SYSTEM.TEMP_SKILL_RUNS_DB))
    monkeypatch.setattr("server.services.temp_skill_run_manager.temp_skill_run_store", store)
    manager = TempSkillRunManager()

    request_id = "req-temp-1"
    store.create_request(
        request_id=request_id,
        engine="gemini",
        parameter={},
        model=None,
        engine_options={},
        runtime_options={},
    )
    manifest = manager.stage_skill_package(request_id, _build_skill_zip())
    assert manifest.id == "demo-temp-skill"
    record = store.get_request(request_id)
    assert record is not None
    assert record["skill_package_path"] is not None
    assert record["staged_skill_dir"] is not None

    manager.cleanup_temp_assets(request_id)
    record = store.get_request(request_id)
    assert record is not None
    assert record["skill_package_path"] is None
    assert record["staged_skill_dir"] is None


def test_reject_oversized_skill_package(monkeypatch, temp_config_dirs):
    store = TempSkillRunStore(db_path=Path(config.SYSTEM.TEMP_SKILL_RUNS_DB))
    monkeypatch.setattr("server.services.temp_skill_run_manager.temp_skill_run_store", store)
    config.defrost()
    config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = 64
    config.freeze()
    manager = TempSkillRunManager()

    request_id = "req-temp-2"
    store.create_request(
        request_id=request_id,
        engine="gemini",
        parameter={},
        model=None,
        engine_options={},
        runtime_options={},
    )
    with pytest.raises(ValueError, match="exceeds size limit"):
        manager.stage_skill_package(request_id, b"x" * 128)


def test_debug_keep_temp_skips_immediate_cleanup(monkeypatch, temp_config_dirs):
    store = TempSkillRunStore(db_path=Path(config.SYSTEM.TEMP_SKILL_RUNS_DB))
    monkeypatch.setattr("server.services.temp_skill_run_manager.temp_skill_run_store", store)
    manager = TempSkillRunManager()

    request_id = "req-temp-3"
    store.create_request(
        request_id=request_id,
        engine="gemini",
        parameter={},
        model=None,
        engine_options={},
        runtime_options={"debug_keep_temp": True},
    )
    manager.stage_skill_package(request_id, _build_skill_zip())
    manager.on_terminal(request_id, RunStatus.SUCCEEDED, debug_keep_temp=True)
    record = store.get_request(request_id)
    assert record is not None
    assert record["status"] == "succeeded"
    assert record["skill_package_path"] is not None


def test_stage_missing_engines_defaults_to_all_supported(monkeypatch, temp_config_dirs):
    store = TempSkillRunStore(db_path=Path(config.SYSTEM.TEMP_SKILL_RUNS_DB))
    monkeypatch.setattr("server.services.temp_skill_run_manager.temp_skill_run_store", store)
    manager = TempSkillRunManager()

    request_id = "req-temp-4"
    store.create_request(
        request_id=request_id,
        engine="gemini",
        parameter={},
        model=None,
        engine_options={},
        runtime_options={},
    )
    manifest = manager.stage_skill_package(
        request_id,
        _build_skill_zip(include_engines=False),
    )
    assert manifest.engines == []
    assert manifest.effective_engines == ["codex", "gemini", "iflow", "opencode"]
