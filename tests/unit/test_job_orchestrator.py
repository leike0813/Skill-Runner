import asyncio
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from server.models import (
    EngineInteractiveProfile,
    EngineInteractiveProfileKind,
    RunCreateRequest,
    RunStatus,
    SkillManifest,
)
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


class AuthRequiredAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=1,
            raw_stdout="",
            raw_stderr="SERVER_OAUTH2_REQUIRED",
            output_file_path=None,
            artifacts_created=[],
            failure_reason="AUTH_REQUIRED",
        )


class TimeoutAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=1,
            raw_stdout="",
            raw_stderr="",
            output_file_path=None,
            artifacts_created=[],
            failure_reason="TIMEOUT",
        )


class TimeoutSuccessLikeAdapter:
    async def run(self, skill, input_data, run_dir, options):
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "partial.txt").write_text("partial")
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"value": "ok"}))
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"value":"ok"}',
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[artifacts_dir / "partial.txt"],
            failure_reason="TIMEOUT",
        )


class RepairSuccessAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"value": "ok"}))
        return EngineRunResult(
            exit_code=0,
            raw_stdout="fenced output",
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[],
            repair_level="deterministic_generic",
        )


class RepairSchemaFailAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps({"value": "not-an-integer"}))
        return EngineRunResult(
            exit_code=0,
            raw_stdout="fenced output",
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[],
            repair_level="deterministic_generic",
        )


class CancelShouldSkipAdapter:
    async def run(self, *args, **kwargs):
        raise AssertionError("Adapter should not execute when cancel_requested is set")


@pytest.fixture(autouse=True)
def _patch_trust_manager(monkeypatch):
    class NoopTrustManager:
        def register_run_folder(self, engine, run_dir):
            return None

        def remove_run_folder(self, engine, run_dir):
            return None

        def cleanup_stale_entries(self, active_run_dirs):
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
async def test_run_job_cancel_requested_before_execution_short_circuits(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_run(run_id, None, "queued")
        local_store.set_cancel_requested(run_id, True)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": CancelShouldSkipAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "canceled"
        assert status_data["error"]["code"] == "CANCELED_BY_USER"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_cancel_run_running_updates_status_and_sets_flag(tmp_path):
    run_id = "run-cancel"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    local_store = RunStore(db_path=tmp_path / "runs.db")
    local_store.create_run(run_id, None, "running")

    class _CancelableAdapter:
        async def cancel_run_process(self, _run_id: str) -> bool:
            return True

    orchestrator = JobOrchestrator()
    orchestrator.adapters = {"codex": _CancelableAdapter()}

    with patch("server.services.job_orchestrator.run_store", local_store):
        accepted = await orchestrator.cancel_run(
            run_id=run_id,
            engine_name="codex",
            run_dir=run_dir,
            status=RunStatus.RUNNING,
            request_id=None,
        )

    status_data = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert accepted is True
    assert local_store.is_cancel_requested(run_id) is True
    assert status_data["status"] == "canceled"
    assert status_data["error"]["code"] == "CANCELED_BY_USER"


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
async def test_run_job_marks_auth_required_error_code(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
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
        orchestrator.adapters = {"codex": AuthRequiredAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] == "AUTH_REQUIRED"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_marks_timeout_error_code(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    old_timeout = config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS = 600
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": TimeoutAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] == "TIMEOUT"
        assert "600s" in result_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS = old_timeout
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_timeout_reason_has_priority_over_exit_code(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]})
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_run(run_id, "cache-key-1", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": TimeoutSuccessLikeAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"hard_timeout_seconds": 15},
                cache_key="cache-key-1",
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] == "TIMEOUT"
        assert "15s" in result_data["error"]["message"]
        assert "artifacts/partial.txt" in result_data["artifacts"]
        assert local_store.get_cached_run("cache-key-1") is None
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


@pytest.mark.asyncio
async def test_run_job_repair_success_sets_warning_and_cacheable(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]})
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_run(run_id, "cache-key-repair", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSuccessAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={},
                cache_key="cache-key-repair",
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert "OUTPUT_REPAIRED_GENERIC" in result_data["validation_warnings"]
        assert "OUTPUT_REPAIRED_GENERIC" in status_data["warnings"]
        assert result_data["repair_level"] == "deterministic_generic"
        assert local_store.get_cached_run("cache-key-repair") == run_id
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_repair_result_still_fails_when_schema_invalid(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]})
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_run(run_id, "cache-key-repair-fail", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSchemaFailAdapter()}

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={},
                cache_key="cache-key-repair-fail",
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert result_data["repair_level"] == "deterministic_generic"
        assert "Output validation error" in result_data["error"]["message"]
        assert "OUTPUT_REPAIRED_GENERIC" not in result_data["validation_warnings"]
        assert local_store.get_cached_run("cache-key-repair-fail") is None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class InteractiveAskAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "ask_user": {
                        "interaction_id": 1,
                        "kind": "choose_one",
                        "prompt": "continue?",
                        "options": [{"label": "Yes", "value": "yes"}],
                    }
                }
            )
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}\n',
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[],
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="thread-1",
            created_at_turn=turn_index,
        )


class InteractiveAskMissingHandleAdapter(InteractiveAskAdapter):
    def extract_session_handle(self, raw_stdout, turn_index):
        raise RuntimeError("SESSION_RESUME_FAILED: missing thread.started")


class InteractiveAskMissingIdAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "ask_user": {
                        "kind": "choose_one",
                        "prompt": "continue?",
                    }
                }
            )
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}\n',
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[],
        )


@pytest.mark.asyncio
async def test_run_job_interactive_waiting_user_persists_profile_and_handle(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_request(
            request_id="req-interactive",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        local_store.update_request_run_id("req-interactive", run_id)
        local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.RESUMABLE,
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        assert status_data["status"] == "waiting_user"
        pending = local_store.get_pending_interaction("req-interactive")
        assert pending is not None
        assert pending["interaction_id"] == 1
        interactions_dir = run_dir / "interactions"
        assert (interactions_dir / "pending.json").exists()
        assert (interactions_dir / "history.jsonl").exists()
        assert (interactions_dir / "runtime_state.json").exists()
        handle = local_store.get_engine_session_handle("req-interactive")
        assert handle is not None
        assert handle["handle_value"] == "thread-1"
        profile = local_store.get_interactive_profile("req-interactive")
        assert profile is not None
        assert profile["kind"] == "resumable"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_invalid_ask_user_does_not_enter_waiting_user(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {"ok": {"type": "boolean"}}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_request(
            request_id="req-interactive-invalid",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        local_store.update_request_run_id("req-interactive-invalid", run_id)
        local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskMissingIdAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.RESUMABLE,
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        assert status_data["status"] == "failed"
        assert local_store.get_pending_interaction("req-interactive-invalid") is None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class InteractiveTwoTurnAdapter:
    async def run(self, skill, input_data, run_dir, options):
        output_path = run_dir / "raw" / "output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if "__interactive_reply_payload" in options:
            output_path.write_text(json.dumps({"value": "ok"}))
            return EngineRunResult(
                exit_code=0,
                raw_stdout='{"type":"item.completed"}',
                raw_stderr="",
                output_file_path=output_path,
                artifacts_created=[],
            )
        output_path.write_text(
            json.dumps(
                {
                    "ask_user": {
                        "interaction_id": 1,
                        "kind": "choose_one",
                        "prompt": "continue?",
                        "options": [{"label": "Yes", "value": "yes"}],
                    }
                }
            )
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}',
            raw_stderr="",
            output_file_path=output_path,
            artifacts_created=[],
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="thread-1",
            created_at_turn=turn_index,
        )


def _build_interactive_skill(tmp_path: Path) -> SkillManifest:
    skill_dir = tmp_path / "skill-interactive"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"value": {"type": "string"}}})
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    return SkillManifest(
        id="test-skill-interactive",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )


def _seed_interactive_request(store: RunStore, run_id: str, skill_id: str) -> None:
    store.create_request(
        request_id="req-turn",
        skill_id=skill_id,
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    store.update_request_run_id("req-turn", run_id)
    store.create_run(run_id, None, "queued")


def _seed_recovery_run(
    store: RunStore,
    *,
    request_id: str,
    run_id: str,
    status: str,
    runtime_options: dict,
    profile: dict | None = None,
    pending: dict | None = None,
    session_handle: dict | None = None,
    process_binding: dict | None = None,
) -> Path:
    store.create_request(
        request_id=request_id,
        skill_id="recovery-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options=runtime_options,
        input_data={},
    )
    store.update_request_run_id(request_id, run_id)
    store.create_run(run_id, None, status)
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": status,
                "updated_at": "2026-02-16T00:00:00",
                "warnings": [],
                "error": None,
            }
        ),
        encoding="utf-8",
    )
    if profile is not None:
        store.set_interactive_profile(request_id, profile)
    if pending is not None:
        store.set_pending_interaction(request_id, pending)
    if session_handle is not None:
        store.set_engine_session_handle(request_id, session_handle)
    if process_binding is not None:
        store.set_sticky_wait_runtime(
            request_id=request_id,
            wait_deadline_at="2099-01-01T00:00:00",
            process_binding=process_binding,
        )
    return run_dir


@pytest.mark.asyncio
async def test_resumable_reacquires_slot_on_reply(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.release_slot", _release)

    skill = _build_interactive_skill(tmp_path)
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        _seed_interactive_request(local_store, run_id, skill.id)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.RESUMABLE,
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={
                    "execution_mode": "interactive",
                    "__interactive_reply_payload": {"value": "yes"},
                    "__interactive_reply_interaction_id": 1,
                },
            )

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "succeeded"
        assert events == ["acquire", "release", "acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_sticky_waiting_keeps_slot(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.release_slot", _release)

    skill = _build_interactive_skill(tmp_path)
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        _seed_interactive_request(local_store, run_id, skill.id)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.STICKY_PROCESS,
            reason="probe_failed",
            session_timeout_sec=1200,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )
            orchestrator.cancel_sticky_watchdog("req-turn")

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "waiting_user"
        assert events == ["acquire"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_sticky_timeout_releases_slot(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.release_slot", _release)

    skill = _build_interactive_skill(tmp_path)
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        _seed_interactive_request(local_store, run_id, skill.id)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.STICKY_PROCESS,
            reason="probe_failed",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={
                    "execution_mode": "interactive",
                    "interactive_wait_timeout_sec": 1,
                },
            )
            await asyncio.sleep(1.2)

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "failed"
        assert status_data["error"]["code"] == "INTERACTION_WAIT_TIMEOUT"
        assert status_data["effective_session_timeout_sec"] == 1
        assert events == ["acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_resumable_strict_false_auto_decides_and_resumes(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.release_slot", _release)

    skill = _build_interactive_skill(tmp_path)
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_request(
            request_id="req-auto-resume",
            skill_id=skill.id,
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={
                "execution_mode": "interactive",
                "interactive_require_user_reply": False,
                "session_timeout_sec": 1,
            },
            input_data={},
        )
        local_store.update_request_run_id("req-auto-resume", run_id)
        local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.RESUMABLE,
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={
                    "execution_mode": "interactive",
                    "interactive_require_user_reply": False,
                    "session_timeout_sec": 1,
                },
            )
            await asyncio.sleep(1.3)

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "succeeded"
        stats = local_store.get_auto_decision_stats("req-auto-resume")
        assert stats["auto_decision_count"] == 1
        assert isinstance(stats["last_auto_decision_at"], str)
        assert events == ["acquire", "release", "acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_sticky_strict_false_auto_decides_and_continues(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.job_orchestrator.concurrency_manager.release_slot", _release)

    skill = _build_interactive_skill(tmp_path)
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_request(
            request_id="req-auto-sticky",
            skill_id=skill.id,
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={
                "execution_mode": "interactive",
                "interactive_require_user_reply": False,
                "session_timeout_sec": 1,
            },
            input_data={},
        )
        local_store.update_request_run_id("req-auto-sticky", run_id)
        local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.STICKY_PROCESS,
            reason="probe_failed",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={
                    "execution_mode": "interactive",
                    "interactive_require_user_reply": False,
                    "session_timeout_sec": 1,
                },
            )
            await asyncio.sleep(1.3)

        status_data = json.loads((Path(config.SYSTEM.RUNS_DIR) / run_id / "status.json").read_text())
        assert status_data["status"] == "succeeded"
        stats = local_store.get_auto_decision_stats("req-auto-sticky")
        assert stats["auto_decision_count"] == 1
        assert isinstance(stats["last_auto_decision_at"], str)
        assert events == ["acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_missing_handle_maps_session_resume_failed(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        run_id = _create_run_with_skill(tmp_path, skill)
        local_store = RunStore(db_path=tmp_path / "runs.db")
        local_store.create_request(
            request_id="req-missing-handle",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        local_store.update_request_run_id("req-missing-handle", run_id)
        local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskMissingHandleAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            kind=EngineInteractiveProfileKind.RESUMABLE,
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = json.loads((run_dir / "status.json").read_text())
        assert status_data["status"] == "failed"
        assert status_data["error"]["code"] == "SESSION_RESUME_FAILED"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_resumable_waiting_user_keeps_waiting(tmp_path):
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        _seed_recovery_run(
            local_store,
            request_id="req-recover-resumable",
            run_id="run-recover-resumable",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"kind": EngineInteractiveProfileKind.RESUMABLE.value, "session_timeout_sec": 1200},
            pending={"interaction_id": 1, "kind": "open_text", "prompt": "continue?"},
            session_handle={
                "engine": "codex",
                "handle_type": "session_id",
                "handle_value": "thread-1",
                "created_at_turn": 1,
            },
        )

        orchestrator = JobOrchestrator()
        with patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        run_state = local_store.get_run("run-recover-resumable")
        assert run_state is not None
        assert run_state["status"] == RunStatus.WAITING_USER.value
        recovery = local_store.get_recovery_info("run-recover-resumable")
        assert recovery["recovery_state"] == "recovered_waiting"
        assert recovery["recovery_reason"] == "resumable_waiting_preserved"
        assert local_store.get_pending_interaction("req-recover-resumable") is not None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_sticky_waiting_user_fails_with_process_lost(tmp_path):
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        run_dir = _seed_recovery_run(
            local_store,
            request_id="req-recover-sticky",
            run_id="run-recover-sticky",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"kind": EngineInteractiveProfileKind.STICKY_PROCESS.value, "session_timeout_sec": 1200},
            pending={"interaction_id": 1, "kind": "open_text", "prompt": "continue?"},
            process_binding={"run_id": "run-recover-sticky", "alive": True},
        )

        orchestrator = JobOrchestrator()
        with patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        status_data = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        assert status_data["status"] == RunStatus.FAILED.value
        assert status_data["error"]["code"] == "INTERACTION_PROCESS_LOST"
        run_state = local_store.get_run("run-recover-sticky")
        assert run_state is not None
        assert run_state["status"] == RunStatus.FAILED.value
        recovery = local_store.get_recovery_info("run-recover-sticky")
        assert recovery["recovery_state"] == "failed_reconciled"
        assert local_store.get_pending_interaction("req-recover-sticky") is None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_running_or_queued_fails_with_restart_interrupted(tmp_path):
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        run_dir = _seed_recovery_run(
            local_store,
            request_id="req-recover-running",
            run_id="run-recover-running",
            status=RunStatus.RUNNING.value,
            runtime_options={"execution_mode": "interactive"},
        )

        orchestrator = JobOrchestrator()
        with patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        status_data = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        assert status_data["status"] == RunStatus.FAILED.value
        assert status_data["error"]["code"] == "ORCHESTRATOR_RESTART_INTERRUPTED"
        recovery = local_store.get_recovery_info("run-recover-running")
        assert recovery["recovery_state"] == "failed_reconciled"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_orphan_cleanup_is_idempotent(tmp_path):
    class CountingCancelAdapter:
        def __init__(self) -> None:
            self.cancel_calls = 0

        async def cancel_run_process(self, run_id: str) -> bool:
            self.cancel_calls += 1
            return True

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        _seed_recovery_run(
            local_store,
            request_id="req-recover-idempotent",
            run_id="run-recover-idempotent",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"kind": EngineInteractiveProfileKind.STICKY_PROCESS.value, "session_timeout_sec": 1200},
            pending={"interaction_id": 2, "kind": "open_text", "prompt": "continue?"},
            process_binding={"run_id": "run-recover-idempotent", "alive": True},
        )

        adapter = CountingCancelAdapter()
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": adapter}
        with patch("server.services.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()
            first_calls = adapter.cancel_calls
            await orchestrator.recover_incomplete_runs_on_startup()
            second_calls = adapter.cancel_calls

        assert first_calls >= 1
        assert second_calls == first_calls
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()
