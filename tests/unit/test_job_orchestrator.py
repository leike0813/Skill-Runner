import json
from pathlib import Path
from unittest.mock import patch
import pytest

from server.models import RunCreateRequest, SkillManifest
from server.services.job_orchestrator import JobOrchestrator
from server.services.run_store import RunStore
from server.services.workspace_manager import workspace_manager
from server.config import config
from server.adapters.base import EngineRunResult


class FailingAdapter:
    async def run(self, *args, **kwargs):
        raise AssertionError("Adapter should not be called on input validation failure")


class DummyAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"value": "bad"}))
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[]
        )


class NoOutputAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            output_file_path=None,
            artifacts_created=[]
        )


class MissingArtifactsAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"value": "ok"}))
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[]
        )


@pytest.fixture(autouse=True)
def _patch_trust_manager(monkeypatch):
    class NoopTrustManager:
        def register_run_folder(self, engine, run_dir):
            return None

        def remove_run_folder(self, engine, run_dir):
            return None

    monkeypatch.setattr("server.services.job_orchestrator.run_folder_trust_manager", NoopTrustManager())


def _create_run_with_skill(tmp_path: Path, skill: SkillManifest) -> str:
    req = RunCreateRequest(skill_id=skill.id, engine="codex", parameter={})
    with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill):
        resp = workspace_manager.create_run(req)
    return resp.run_id


@pytest.mark.asyncio
async def test_run_job_missing_required_input_marks_failed(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    input_schema = {
        "type": "object",
        "properties": {"input_file": {"type": "string"}},
        "required": ["input_file"]
    }
    (skill_dir / "input.schema.json").write_text(json.dumps(input_schema))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": FailingAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        status_path = Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json"
        status_data = json.loads(status_path.read_text())
        assert status_data["status"] == "failed"
        assert "Missing required input files" in status_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_writes_output_warnings(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    output_schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"]
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": DummyAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert result_data["error"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_records_artifacts_in_result(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts" / "extra.txt").write_text("artifact")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": DummyAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert "artifacts/extra.txt" in result_data["artifacts"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_fails_when_output_json_missing(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": NoOutputAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert "Output JSON missing" in result_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_fails_when_required_artifacts_missing(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    output_schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"]
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        artifacts=[{"role": "result_file", "pattern": "required.txt", "required": True}],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": MissingArtifactsAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert "Missing required artifacts" in result_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_registers_and_cleans_trust(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json"
        }
    )

    class Recorder:
        def __init__(self):
            self.events = []

        def register_run_folder(self, engine, run_dir):
            self.events.append(("register", engine, str(run_dir)))

        def remove_run_folder(self, engine, run_dir):
            self.events.append(("remove", engine, str(run_dir)))

    recorder = Recorder()
    monkeypatch.setattr("server.services.job_orchestrator.run_folder_trust_manager", recorder)

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": DummyAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        assert any(event[0] == "register" and event[1] == "codex" for event in recorder.events)
        assert any(event[0] == "remove" and event[1] == "codex" for event in recorder.events)
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()
