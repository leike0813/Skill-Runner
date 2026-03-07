import asyncio
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from server.models import (
    AdapterTurnInteraction,
    AdapterTurnOutcome,
    AdapterTurnResult,
    EngineInteractiveProfile,
    InteractiveErrorCode,
    RunCreateRequest,
    RunStatus,
    SkillManifest,
)
from server.services.orchestration.job_orchestrator import JobOrchestrator
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.workspace_manager import workspace_manager
from server.config import config
from server.runtime.adapter.types import EngineRunResult


def _final_engine_result(
    *,
    final_data: dict[str, object],
    raw_stdout: str = "",
    raw_stderr: str = "",
    exit_code: int = 0,
    artifacts_created: list[Path] | None = None,
    failure_reason: str | None = None,
    repair_level: str = "none",
    runtime_warnings: list[dict[str, str]] | None = None,
) -> EngineRunResult:
    return EngineRunResult(
        exit_code=exit_code,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        artifacts_created=artifacts_created or [],
        failure_reason=failure_reason,
        repair_level=repair_level,
        runtime_warnings=runtime_warnings,
        turn_result=AdapterTurnResult(
            outcome=AdapterTurnOutcome.FINAL,
            final_data=final_data,
            repair_level=repair_level,
            failure_reason=failure_reason,
        ),
    )


def _ask_user_engine_result(
    *,
    interaction: dict[str, object],
    raw_stdout: str = "",
    raw_stderr: str = "",
    exit_code: int = 0,
    artifacts_created: list[Path] | None = None,
    failure_reason: str | None = None,
    repair_level: str = "none",
) -> EngineRunResult:
    return EngineRunResult(
        exit_code=exit_code,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        artifacts_created=artifacts_created or [],
        failure_reason=failure_reason,
        repair_level=repair_level,
        turn_result=AdapterTurnResult(
            outcome=AdapterTurnOutcome.ASK_USER,
            interaction=AdapterTurnInteraction.model_validate(interaction),
            repair_level=repair_level,
            failure_reason=failure_reason,
        ),
    )


class FailingAdapter:
    async def run(self, *args, **kwargs):
        raise AssertionError("Adapter should not be called on input validation failure")


class DummyAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(final_data={"value": "bad"})


class NoOutputAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            artifacts_created=[]
        )


class MissingArtifactsAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(final_data={"value": "ok"})


class AutofixArtifactPathAdapter:
    async def run(self, skill, input_data, run_dir, options):
        uploads_dir = run_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        digest_path = uploads_dir / "digest.md"
        digest_path.write_text("digest content", encoding="utf-8")
        return _final_engine_result(
            final_data={"digest_path": str(digest_path)},
        )


class AutofixArtifactTargetExistsAdapter:
    async def run(self, skill, input_data, run_dir, options):
        uploads_dir = run_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        digest_path = uploads_dir / "digest.md"
        digest_path.write_text("digest content", encoding="utf-8")
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "digest.md").mkdir(parents=True, exist_ok=True)
        return _final_engine_result(
            final_data={"digest_path": str(digest_path)},
        )


class AutofixArtifactOutsideRunDirAdapter:
    async def run(self, skill, input_data, run_dir, options):
        outside_file = run_dir.parent / "outside-digest.md"
        outside_file.write_text("outside", encoding="utf-8")
        return _final_engine_result(
            final_data={"digest_path": str(outside_file)},
        )


class AuthRequiredAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=1,
            raw_stdout="",
            raw_stderr="SERVER_OAUTH2_REQUIRED",
            artifacts_created=[],
            failure_reason="AUTH_REQUIRED",
        )


class TimeoutAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=1,
            raw_stdout="",
            raw_stderr="",
            artifacts_created=[],
            failure_reason="TIMEOUT",
        )


class TimeoutSuccessLikeAdapter:
    async def run(self, skill, input_data, run_dir, options):
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "partial.txt").write_text("partial")
        return _final_engine_result(
            final_data={"value": "ok"},
            raw_stdout='{"value":"ok"}',
            artifacts_created=[artifacts_dir / "partial.txt"],
            failure_reason="TIMEOUT",
        )


class RepairSuccessAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(
            final_data={"value": "ok"},
            raw_stdout="fenced output",
            repair_level="deterministic_generic",
        )


class RepairSchemaFailAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(
            final_data={"value": "not-an-integer"},
            raw_stdout="fenced output",
            repair_level="deterministic_generic",
        )


class RuntimeDependenciesWarningAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(
            final_data={"value": "ok"},
            runtime_warnings=[
                {
                    "code": "RUNTIME_DEPENDENCIES_INJECTION_FAILED",
                    "detail": "uv dependency probe timed out",
                }
            ],
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

    monkeypatch.setattr("server.services.orchestration.job_orchestrator.run_folder_trust_manager", NoopTrustManager())


def _create_run_with_skill(tmp_path: Path, skill: SkillManifest) -> str:
    req = RunCreateRequest(skill_id=skill.id, engine="codex", parameter={})
    with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
        resp = workspace_manager.create_run(req)
    return resp.run_id


def _read_state_data(run_dir: Path) -> dict:
    return json.loads((run_dir / ".state" / "state.json").read_text(encoding="utf-8"))


def _write_state_data(
    run_dir: Path,
    *,
    status: str,
    request_id: str | None = None,
    current_attempt: int = 1,
    error: object = None,
    warnings: list[object] | None = None,
) -> None:
    state_dir = run_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": request_id or f"req-{run_dir.name}",
        "run_id": run_dir.name,
        "status": status,
        "updated_at": "2026-01-01T00:00:00",
        "current_attempt": current_attempt,
        "state_phase": {
            "waiting_auth_phase": None,
            "dispatch_phase": None,
        },
        "pending": {
            "owner": None,
            "interaction_id": None,
            "auth_session_id": None,
            "payload": None,
        },
        "resume": {
            "resume_ticket_id": None,
            "resume_cause": None,
            "source_attempt": None,
            "target_attempt": None,
        },
        "runtime": {
            "conversation_mode": "session",
            "requested_execution_mode": None,
            "effective_execution_mode": None,
            "effective_interactive_require_user_reply": None,
            "effective_interactive_reply_timeout_sec": None,
            "effective_session_timeout_sec": None,
        },
        "error": error,
        "warnings": warnings or [],
    }
    (state_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        status_data = _read_state_data(Path(config.SYSTEM.RUNS_DIR) / run_id)
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
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
        await local_store.create_run(run_id, None, "queued")
        await local_store.set_cancel_requested(run_id, True)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": CancelShouldSkipAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        status_data = _read_state_data(Path(config.SYSTEM.RUNS_DIR) / run_id)
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
    _write_state_data(run_dir, status="running")
    local_store = RunStore(db_path=tmp_path / "runs.db")
    await local_store.create_run(run_id, None, "running")

    class _CancelableAdapter:
        async def cancel_run_process(self, _run_id: str) -> bool:
            return True

    orchestrator = JobOrchestrator()
    orchestrator.adapters = {"codex": _CancelableAdapter()}

    with patch("server.services.orchestration.job_orchestrator.run_store", local_store):
        accepted = await orchestrator.cancel_run(
            run_id=run_id,
            engine_name="codex",
            run_dir=run_dir,
            status=RunStatus.RUNNING,
            request_id=None,
        )

    status_data = _read_state_data(run_dir)
    assert accepted is True
    assert await local_store.is_cancel_requested(run_id) is True
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert "Missing required artifacts" in result_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_autofix_moves_required_artifact_to_canonical_path(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    output_schema = {
        "type": "object",
        "properties": {
            "digest_path": {
                "type": "string",
                "x-type": "artifact",
                "x-filename": "digest.md",
            }
        },
        "required": ["digest_path"],
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        artifacts=[{"role": "digest", "pattern": "digest.md", "required": True}],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
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
        orchestrator.adapters = {"codex": AutofixArtifactPathAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert (run_dir / "artifacts" / "digest.md").is_file()
        assert not (run_dir / "uploads" / "digest.md").exists()
        assert result_data["data"]["digest_path"] == str(run_dir / "artifacts" / "digest.md")
        assert "OUTPUT_ARTIFACT_PATH_REPAIRED" in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_autofix_target_exists_keeps_existing_and_warns(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    output_schema = {
        "type": "object",
        "properties": {
            "digest_path": {
                "type": "string",
                "x-type": "artifact",
                "x-filename": "digest.md",
            }
        },
        "required": ["digest_path"],
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        artifacts=[{"role": "digest", "pattern": "digest.md", "required": True}],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
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
        orchestrator.adapters = {"codex": AutofixArtifactTargetExistsAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert "Missing required artifacts" in result_data["error"]["message"]
        assert "OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS" in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_autofix_rejects_outside_run_dir_path(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    output_schema = {
        "type": "object",
        "properties": {
            "digest_path": {
                "type": "string",
                "x-type": "artifact",
                "x-filename": "digest.md",
            }
        },
        "required": ["digest_path"],
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engines=["codex"],
        artifacts=[{"role": "digest", "pattern": "digest.md", "required": True}],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
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
        orchestrator.adapters = {"codex": AutofixArtifactOutsideRunDirAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert "Missing required artifacts" in result_data["error"]["message"]
        assert "OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR" in result_data["validation_warnings"]
        assert not (run_dir / "artifacts" / "digest.md").exists()
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] == "AUTH_REQUIRED"
        orchestrator_events_path = run_dir / ".audit" / "orchestrator_events.1.jsonl"
        orchestrator_events = [
            json.loads(line)
            for line in orchestrator_events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        terminal_rows = [
            row
            for row in orchestrator_events
            if row.get("type") == "lifecycle.run.terminal"
        ]
        assert terminal_rows
        terminal_data = terminal_rows[-1]["data"]
        assert terminal_data["status"] == "failed"
        assert terminal_data["code"] == "AUTH_REQUIRED"
        assert "authentication is required" in terminal_data["message"]
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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
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
        await local_store.create_run(run_id, "cache-key-1", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": TimeoutSuccessLikeAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
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
        assert await local_store.get_cached_run("cache-key-1") is None
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
    monkeypatch.setattr("server.services.orchestration.job_orchestrator.run_folder_trust_manager", recorder)

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

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
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
        await local_store.create_run(run_id, "cache-key-repair", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSuccessAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={},
                cache_key="cache-key-repair",
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert "OUTPUT_REPAIRED_GENERIC" in result_data["validation_warnings"]
        assert "OUTPUT_REPAIRED_GENERIC" in status_data["warnings"]
        assert result_data["repair_level"] == "deterministic_generic"
        assert await local_store.get_cached_run("cache-key-repair") == run_id
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_records_runtime_dependency_injection_warning(tmp_path):
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
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RuntimeDependenciesWarningAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", RunStore(db_path=tmp_path / "runs.db")):
            await orchestrator.run_job(run_id, "test-skill", "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text(encoding="utf-8"))
        assert result_data["status"] == "success"
        assert "RUNTIME_DEPENDENCIES_INJECTION_FAILED" in result_data["validation_warnings"]
        orchestrator_events_path = run_dir / ".audit" / "orchestrator_events.1.jsonl"
        orchestrator_events = [
            json.loads(line)
            for line in orchestrator_events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(
            row.get("type") == "diagnostic.warning"
            and row.get("data", {}).get("code") == "RUNTIME_DEPENDENCIES_INJECTION_FAILED"
            for row in orchestrator_events
        )
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
        await local_store.create_run(run_id, "cache-key-repair-fail", "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSchemaFailAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={},
                cache_key="cache-key-repair-fail",
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert result_data["repair_level"] == "deterministic_generic"
        assert "Output validation error" in result_data["error"]["message"]
        assert "OUTPUT_REPAIRED_GENERIC" not in result_data["validation_warnings"]
        assert await local_store.get_cached_run("cache-key-repair-fail") is None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class InteractiveAskAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _ask_user_engine_result(
            interaction={
                "interaction_id": 1,
                "kind": "choose_one",
                "prompt": "continue?",
                "options": [{"label": "Yes", "value": "yes"}],
            },
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}\n',
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


class InteractiveAskSessionInStderrAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _ask_user_engine_result(
            interaction={
                "interaction_id": 1,
                "kind": "open_text",
                "prompt": "continue?",
            },
            raw_stdout="assistant: please continue\n",
            raw_stderr='{"session-id":"iflow-session-1"}\n',
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        match = re.search(r'"session-id"\s*:\s*"([^"]+)"', raw_stdout)
        if not match:
            raise RuntimeError("SESSION_RESUME_FAILED: missing iflow session-id")
        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=match.group(1),
            created_at_turn=turn_index,
        )


class InteractiveAskMissingIdAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}\n',
            raw_stderr="",
            artifacts_created=[],
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.ERROR,
                final_data={"code": "ADAPTER_TURN_ERROR", "message": "invalid ask_user payload: missing interaction_id"},
                failure_reason="ADAPTER_TURN_ERROR",
            ),
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="thread-1",
            created_at_turn=turn_index,
        )


@pytest.mark.asyncio
async def test_run_job_interactive_waiting_user_persists_profile_and_handle(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }
        )
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
        await local_store.create_request(
            request_id="req-interactive",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        await local_store.update_request_run_id("req-interactive", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        pending = await local_store.get_pending_interaction("req-interactive")
        assert pending is not None
        assert pending["interaction_id"] == 1
        assert status_data["pending"]["owner"] == "waiting_user"
        assert status_data["pending"]["interaction_id"] == 1
        handle = await local_store.get_engine_session_handle("req-interactive")
        assert handle is not None
        assert handle["handle_value"] == "thread-1"
        profile = await local_store.get_interactive_profile("req-interactive")
        assert profile is not None
        assert profile["session_timeout_sec"] == int(config.SYSTEM.SESSION_TIMEOUT_SEC)
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_waiting_user_session_handle_can_be_extracted_from_stderr(tmp_path):
    skill_dir = tmp_path / "skill-stderr-session"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-stderr-session",
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
        await local_store.create_request(
            request_id="req-interactive-stderr-session",
            skill_id="test-skill-stderr-session",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        await local_store.update_request_run_id("req-interactive-stderr-session", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskSessionInStderrAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill-stderr-session",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        assert status_data["error"] is None
        pending = await local_store.get_pending_interaction("req-interactive-stderr-session")
        assert pending is not None
        handle = await local_store.get_engine_session_handle("req-interactive-stderr-session")
        assert handle is not None
        assert handle["handle_value"] == "iflow-session-1"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_missing_interaction_id_falls_back_to_waiting_user(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            }
        )
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
        await local_store.create_request(
            request_id="req-interactive-invalid",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        await local_store.update_request_run_id("req-interactive-invalid", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskMissingIdAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        pending = await local_store.get_pending_interaction("req-interactive-invalid")
        assert pending is not None
        assert pending["interaction_id"] == 1
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class DoneMarkerOutputAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(
            final_data={"value": 7, "__SKILL_DONE__": True},
            raw_stdout='{"type":"item.completed","item":{"type":"agent_message","text":"{\\"value\\":7,\\"__SKILL_DONE__\\":true}"}}\n',
        )


class _CodexAgentMessageParseMixin:
    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
        _ = pty_raw
        assistant_messages = []
        session_id = None
        for stream_name, raw in (("stdout", stdout_raw), ("stderr", stderr_raw)):
            text = raw.decode("utf-8", errors="replace")
            cursor = 0
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    cursor += len(line) + 1
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    cursor += len(line) + 1
                    continue
                if not isinstance(payload, dict):
                    cursor += len(line) + 1
                    continue
                if payload.get("type") == "thread.started":
                    thread_id = payload.get("thread_id")
                    if isinstance(thread_id, str) and thread_id.strip():
                        session_id = thread_id.strip()
                if payload.get("type") == "item.completed":
                    item = payload.get("item")
                    if isinstance(item, dict) and item.get("type") == "agent_message":
                        msg_text = item.get("text")
                        if isinstance(msg_text, str) and msg_text.strip():
                            assistant_messages.append(
                                {
                                    "text": msg_text,
                                    "raw_ref": {
                                        "stream": stream_name,
                                        "byte_from": cursor,
                                        "byte_to": cursor + len(line),
                                    },
                                }
                            )
                cursor += len(line) + 1
        return {
            "parser": "codex_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": assistant_messages,
            "raw_rows": [],
            "diagnostics": [],
            "structured_types": [],
        }


class EscapedDoneMarkerStreamOnlyAdapter(_CodexAgentMessageParseMixin):
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"item.completed","item":{"type":"agent_message","text":"{\\"value\\":\\"stream-marker-only\\",\\"__SKILL_DONE__\\": true}"}}\n',
            raw_stderr="",
            artifacts_created=[],
        )


class EscapedDoneMarkerWithInvalidOutputAdapter(_CodexAgentMessageParseMixin):
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"item.completed","item":{"type":"agent_message","text":"{\\"value\\":\\"bad\\",\\"__SKILL_DONE__\\": true}"}}\n',
            raw_stderr="",
            artifacts_created=[],
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.FINAL,
                final_data={"value": 7, "__SKILL_DONE__": True},
            ),
        )


class ToolUseDoneMarkerEchoAdapter(_CodexAgentMessageParseMixin):
    async def run(self, skill, input_data, run_dir, options):
        tool_use_line = json.dumps(
            {
                "type": "tool_use",
                "part": {
                    "type": "tool",
                    "tool": "skill",
                    "state": {
                        "output": 'Injected contract: "__SKILL_DONE__": true',
                    },
                },
            },
            ensure_ascii=False,
        )
        message_line = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "请先告诉我你的基本信息，我再继续。",
                },
            },
            ensure_ascii=False,
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout=f"{tool_use_line}\n{message_line}\n",
            raw_stderr="",
            artifacts_created=[],
        )


class InteractiveSoftCompletionAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return _final_engine_result(
            final_data={"value": "soft-complete"},
            raw_stdout='{"type":"item.completed","item":{"type":"agent_message","text":"soft-complete"}}\n',
        )


class InteractiveNoEvidenceAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            artifacts_created=[],
        )


class InteractiveYamlAskUserSignalAdapter:
    async def run(self, skill, input_data, run_dir, options):
        stdout = (
            "<ASK_USER_YAML>\n"
            "ask_user:\n"
            "  interaction_id: 3\n"
            "  kind: open_text\n"
            "  prompt: Please provide missing details.\n"
            "</ASK_USER_YAML>\n"
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout=stdout,
            raw_stderr="",
            artifacts_created=[],
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.FINAL,
                final_data={"note": "this still passes permissive schema"},
            ),
        )


@pytest.mark.asyncio
async def test_run_job_output_validation_strips_done_marker(tmp_path):
    skill_dir = tmp_path / "skill-done-marker"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-done-marker",
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": DoneMarkerOutputAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(run_id, skill.id, "codex", options={})

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert result_data["data"] == {"value": 7}
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_escaped_stream_done_marker_completes_without_soft_warning(tmp_path):
    skill_dir = tmp_path / "skill-escaped-stream-marker"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-escaped-stream-marker",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": EscapedDoneMarkerStreamOnlyAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert result_data["data"] == {"value": "stream-marker-only"}
        assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" not in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_done_marker_with_invalid_output_fails_not_waiting(tmp_path):
    skill_dir = tmp_path / "skill-done-marker-invalid-output"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-done-marker-invalid-output",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": EscapedDoneMarkerWithInvalidOutputAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert result_data["status"] == "failed"
        assert "Output validation error" in result_data["error"]["message"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_tool_use_done_marker_echo_does_not_complete(tmp_path):
    skill_dir = tmp_path / "skill-tool-use-done-marker-echo"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-tool-use-done-marker-echo",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
        max_attempt=3,
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": ToolUseDoneMarkerEchoAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text())
        assert status_data["status"] == "waiting_user"
        assert status_data["error"] is None
        assert status_data["pending"]["owner"] == "waiting_user"
        assert meta_data["completion"]["done_marker_found"] is False
        assert meta_data["completion"]["reason_code"] == "WAITING_USER_INPUT"
        assert status_data["pending"]["interaction_id"] == 1
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_soft_completion_without_done_marker(tmp_path):
    skill_dir = tmp_path / "skill-soft-complete"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-soft-complete",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveSoftCompletionAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert result_data["data"] == {"value": "soft-complete"}
        assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_waiting_when_no_completion_evidence(tmp_path):
    skill_dir = tmp_path / "skill-interactive-no-evidence"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-interactive-no-evidence",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
        max_attempt=3,
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveNoEvidenceAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        assert status_data["error"] is None
        assert status_data["pending"]["owner"] == "waiting_user"
        assert status_data["pending"]["interaction_id"] == 1
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_max_attempt_exceeded_marks_failed(tmp_path):
    skill_dir = tmp_path / "skill-interactive-max-attempt"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-interactive-max-attempt",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
        max_attempt=1,
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveNoEvidenceAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "failed"
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_auto_succeeds_without_done_marker_when_output_valid(tmp_path):
    skill_dir = tmp_path / "skill-auto-soft-complete"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-auto-soft-complete",
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveSoftCompletionAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "auto"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert result_data["data"] == {"value": "soft-complete"}
        assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" not in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_yaml_ask_user_is_pending_enrichment_only(tmp_path):
    skill_dir = tmp_path / "skill-interactive-yaml-ask-user-enrichment"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-interactive-yaml-ask-user-enrichment",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveYamlAskUserSignalAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        assert status_data["pending"]["owner"] == "waiting_user"
        assert status_data["pending"]["interaction_id"] == 3
        assert status_data["pending"]["payload"]["prompt"] == "Please provide missing details."
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_yaml_ask_user_does_not_block_soft_completion(tmp_path):
    skill_dir = tmp_path / "skill-interactive-yaml-ask-user-soft-complete"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}})
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-interactive-yaml-ask-user-soft-complete",
        path=skill_dir,
        engines=["codex"],
        execution_modes=["interactive"],
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
        await local_store.create_run(run_id, None, "queued")
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveYamlAskUserSignalAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text())
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in result_data["validation_warnings"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class InteractiveDirectStringInteractionAdapter:
    async def run(self, skill, input_data, run_dir, options):
        return EngineRunResult(
            exit_code=0,
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}\n',
            raw_stderr="",
            artifacts_created=[],
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.FINAL,
                final_data={
                    "interaction_id": "demo-interactive-1",
                    "kind": "open_text",
                    "prompt": "Please share a short self-introduction.",
                },
            ),
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="thread-1",
            created_at_turn=turn_index,
        )


@pytest.mark.asyncio
async def test_run_job_interactive_direct_string_interaction_id_enters_waiting_user(tmp_path):
    skill_dir = tmp_path / "skill-direct-interaction"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"advise": {"type": "string"}},
                "required": ["advise"],
                "additionalProperties": False,
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    skill = SkillManifest(
        id="test-skill-direct-interaction",
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
        await local_store.create_request(
            request_id="req-direct-interactive",
            skill_id=skill.id,
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        await local_store.update_request_run_id("req-direct-interactive", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveDirectStringInteractionAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "waiting_user"
        pending = await local_store.get_pending_interaction("req-direct-interactive")
        assert pending is not None
        assert pending["interaction_id"] == 1
        assert pending["prompt"] == "Please share a short self-introduction."
        assert pending["context"]["external_interaction_id"] == "demo-interactive-1"
        assert pending["context"]["interaction_id_source"] == "fallback"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


class InteractiveTwoTurnAdapter:
    async def run(self, skill, input_data, run_dir, options):
        if "__interactive_reply_payload" in options:
            return _final_engine_result(
                final_data={"value": "ok", "__SKILL_DONE__": True},
                raw_stdout='{"type":"item.completed"}',
            )
        return _ask_user_engine_result(
            interaction={
                "interaction_id": 1,
                "kind": "choose_one",
                "prompt": "continue?",
                "options": [{"label": "Yes", "value": "yes"}],
            },
            raw_stdout='{"type":"thread.started","thread_id":"thread-1"}',
        )

    def extract_session_handle(self, raw_stdout, turn_index):
        from server.models import EngineSessionHandle, EngineSessionHandleType

        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="thread-1",
            created_at_turn=turn_index,
        )


def test_extract_pending_interaction_accepts_hint_without_prompt():
    orchestrator = JobOrchestrator()
    payload = {
        "ask_user": {
            "interaction_id": 2,
            "kind": "open_text",
            "ui_hints": {"hint": "请先简要介绍你的情况。"},
        }
    }
    extracted = orchestrator._extract_pending_interaction(payload, fallback_interaction_id=2)
    assert extracted is not None
    assert extracted["interaction_id"] == 2
    assert extracted["prompt"] == "Please reply to continue."
    assert extracted["ui_hints"]["hint"] == "请先简要介绍你的情况。"


def test_extract_pending_interaction_accepts_direct_payload_with_hint():
    orchestrator = JobOrchestrator()
    payload = {
        "interaction_id": 3,
        "kind": "open_text",
        "ui_hints": {"hint": "请补充你的核心诉求。"},
    }
    extracted = orchestrator._extract_pending_interaction(payload, fallback_interaction_id=3)
    assert extracted is not None
    assert extracted["interaction_id"] == 3
    assert extracted["prompt"] == "Please reply to continue."
    assert extracted["ui_hints"]["hint"] == "请补充你的核心诉求。"


class EscapedNdjsonAdapterForHint:
    def parse_runtime_stream(self, stdout_raw, stderr_raw, pty_raw):
        _ = stdout_raw
        _ = stderr_raw
        _ = pty_raw
        return {
            "assistant_messages": [
                {
                    "text": (
                        "先收集一点信息。\n\n"
                        "<ASK_USER_YAML>\n"
                        "ask_user:\n"
                        "  kind: open_text\n"
                        "  ui_hints:\n"
                        "    type: string\n"
                        "    hint: \"例如：男，38，工程师\"\n"
                        "</ASK_USER_YAML>"
                    )
                }
            ]
        }


def test_extract_pending_interaction_from_stream_prefers_parser_text_for_hint():
    orchestrator = JobOrchestrator()
    raw_stdout = (
        '{"type":"item.completed","item":{"type":"agent_message","text":"'
        '先收集一点信息。\\n\\n<ASK_USER_YAML>\\nask_user:\\n  kind: open_text\\n  ui_hints:\\n'
        '    type: string\\n    hint: \\"例如：男，38，工程师\\"\\n</ASK_USER_YAML>"}}'
    )
    extracted = orchestrator._extract_pending_interaction_from_stream(
        adapter=EscapedNdjsonAdapterForHint(),
        raw_stdout=raw_stdout,
        raw_stderr="",
        fallback_interaction_id=5,
    )
    assert extracted is not None
    assert extracted["interaction_id"] == 5
    assert extracted["prompt"] == "Please reply to continue."
    assert extracted["ui_hints"]["hint"] == "例如：男，38，工程师"


def _build_interactive_skill(tmp_path: Path) -> SkillManifest:
    skill_dir = tmp_path / "skill-interactive"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }
        )
    )
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    return SkillManifest(
        id="test-skill-interactive",
        path=skill_dir,
        engines=["codex"],
        schemas={"input": "input.schema.json", "parameter": "parameter.schema.json", "output": "output.schema.json"},
    )


def test_load_skill_from_run_dir_reads_workspace_manifest(tmp_path):
    run_dir = tmp_path / "run-resume"
    skill_id = "temp-resume-skill"
    skill_dir = run_dir / ".codex" / "skills" / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("demo", encoding="utf-8")
    (assets_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (assets_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (assets_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"ok": {"type": "boolean"}}}),
        encoding="utf-8",
    )
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "name": "Temp Resume Skill",
                "version": "0.1.0",
                "engines": ["codex"],
                "execution_modes": ["interactive"],
                "schemas": {
                    "input": "assets/input.schema.json",
                    "parameter": "assets/parameter.schema.json",
                    "output": "assets/output.schema.json",
                },
            }
        ),
        encoding="utf-8",
    )

    orchestrator = JobOrchestrator()
    manifest = orchestrator._load_skill_from_run_dir(
        run_dir=run_dir,
        skill_id=skill_id,
        engine_name="codex",
    )
    assert manifest is not None
    assert manifest.id == skill_id
    assert manifest.path == skill_dir


def _seed_run_dir_skill(run_dir: Path, skill: SkillManifest) -> None:
    skill_dir = run_dir / ".codex" / "skills" / skill.id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("demo", encoding="utf-8")
    for schema_name, relative_path in (skill.schemas or {}).items():
        source_path = skill.path / relative_path
        target_path = assets_dir / Path(relative_path).name
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill.id,
                "name": skill.id,
                "version": "0.1.0",
                "engines": skill.engines,
                "execution_modes": ["interactive"],
                "schemas": {
                    schema_name: f"assets/{Path(relative_path).name}"
                    for schema_name, relative_path in (skill.schemas or {}).items()
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_run_job_temp_resume_loads_skill_from_run_dir_when_registry_misses(tmp_path, monkeypatch):
    skill = _build_interactive_skill(tmp_path)
    monkeypatch.setattr(
        "server.services.orchestration.job_orchestrator.concurrency_manager.acquire_slot",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.services.orchestration.job_orchestrator.concurrency_manager.release_slot",
        AsyncMock(return_value=None),
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
        _seed_run_dir_skill(run_dir, skill)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSuccessAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=None):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
                temp_request_id="temp-req-1",
            )

        status_data = _read_state_data(run_dir)
        result_data = json.loads((run_dir / "result" / "result.json").read_text(encoding="utf-8"))
        assert status_data["status"] == "succeeded"
        assert result_data["status"] == "success"
        assert result_data["data"] == {"value": "ok"}
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_failure_overwrites_stale_waiting_auth_result(tmp_path):
    skill = _build_interactive_skill(tmp_path)
    with patch("server.services.orchestration.job_orchestrator.concurrency_manager.acquire_slot", new=AsyncMock(return_value=None)), \
         patch("server.services.orchestration.job_orchestrator.concurrency_manager.release_slot", new=AsyncMock(return_value=None)):

        old_runs_dir = config.SYSTEM.RUNS_DIR
        old_runs_db = config.SYSTEM.RUNS_DB
        config.defrost()
        config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
        config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
        config.freeze()
        try:
            run_id = _create_run_with_skill(tmp_path, skill)
            run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
            stale_result_path = run_dir / "result" / "result.json"
            stale_result_path.parent.mkdir(parents=True, exist_ok=True)
            stale_result_path.write_text(
                json.dumps(
                    {
                        "status": "waiting_auth",
                        "data": {"message": "stale auth wrapper"},
                        "artifacts": [],
                        "repair_level": "none",
                        "validation_warnings": [],
                        "error": None,
                        "pending_interaction": None,
                        "pending_auth_method_selection": {"phase": "method_selection"},
                        "pending_auth": None,
                    }
                ),
                encoding="utf-8",
            )
            orchestrator = JobOrchestrator()

            with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=None):
                await orchestrator.run_job(run_id, skill.id, "codex", options={})

            status_data = _read_state_data(run_dir)
            result_data = json.loads(stale_result_path.read_text(encoding="utf-8"))
            assert status_data["status"] == "failed"
            assert result_data["status"] == "failed"
            assert result_data["data"] is None
            assert "pending_auth_method_selection" not in result_data
            assert "pending_auth" not in result_data
            assert "not found during execution" in result_data["error"]["message"]
        finally:
            config.defrost()
            config.SYSTEM.RUNS_DIR = old_runs_dir
            config.SYSTEM.RUNS_DB = old_runs_db
            config.freeze()


async def _seed_interactive_request(store: RunStore, run_id: str, skill_id: str) -> None:
    await store.create_request(
        request_id="req-turn",
        skill_id=skill_id,
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    await store.update_request_run_id("req-turn", run_id)
    await store.create_run(run_id, None, "queued")


async def _seed_recovery_run(
    store: RunStore,
    *,
    request_id: str,
    run_id: str,
    status: str,
    runtime_options: dict,
    profile: dict | None = None,
    pending: dict | None = None,
    session_handle: dict | None = None,
) -> Path:
    await store.create_request(
        request_id=request_id,
        skill_id="recovery-skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options=runtime_options,
        input_data={},
    )
    await store.update_request_run_id(request_id, run_id)
    await store.create_run(run_id, None, status)
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_data(run_dir, status=status, request_id=request_id)
    if profile is not None:
        await store.set_interactive_profile(request_id, profile)
    if pending is not None:
        await store.set_pending_interaction(request_id, pending)
    if session_handle is not None:
        await store.set_engine_session_handle(request_id, session_handle)
    return run_dir


@pytest.mark.asyncio
async def test_resumable_reacquires_slot_on_reply(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.release_slot", _release)

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
        await _seed_interactive_request(local_store, run_id, skill.id)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
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

        status_data = _read_state_data(Path(config.SYSTEM.RUNS_DIR) / run_id)
        assert status_data["status"] == "succeeded"
        assert events == ["acquire", "release", "acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_missing_run_dir_releases_slot_and_does_not_block_following_run(monkeypatch, tmp_path):
    events: list[str] = []

    async def _acquire():
        events.append("acquire")

    async def _release():
        events.append("release")

    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.release_slot", _release)

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
        await _seed_interactive_request(local_store, run_id, skill.id)
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": RepairSuccessAdapter()}
        original_get_run_dir = workspace_manager.get_run_dir

        def _get_run_dir(target_run_id: str):
            if target_run_id == "missing-run":
                return None
            return original_get_run_dir(target_run_id)

        monkeypatch.setattr(
            "server.services.orchestration.job_orchestrator.workspace_manager.get_run_dir",
            _get_run_dir,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job("missing-run", skill.id, "codex", options={"execution_mode": "interactive"})
            await orchestrator.run_job("missing-run", skill.id, "codex", options={"execution_mode": "interactive"})
            await orchestrator.run_job(run_id, skill.id, "codex", options={"execution_mode": "interactive"})

        status_data = _read_state_data(Path(config.SYSTEM.RUNS_DIR) / run_id)
        assert status_data["status"] == "succeeded"
        assert events == ["acquire", "release", "acquire", "release", "acquire", "release"]
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

    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.orchestration.job_orchestrator.concurrency_manager.release_slot", _release)

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
        await local_store.create_request(
            request_id="req-auto-resume",
            skill_id=skill.id,
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={
                "execution_mode": "interactive",
                "interactive_auto_reply": True,
                "interactive_reply_timeout_sec": 1,
            },
            input_data={},
        )
        await local_store.update_request_run_id("req-auto-resume", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveTwoTurnAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={
                    "execution_mode": "interactive",
                    "interactive_auto_reply": True,
                    "interactive_reply_timeout_sec": 1,
                },
            )
            await asyncio.sleep(1.3)

        status_data = _read_state_data(Path(config.SYSTEM.RUNS_DIR) / run_id)
        assert status_data["status"] == "succeeded"
        stats = await local_store.get_auto_decision_stats("req-auto-resume")
        assert stats["auto_decision_count"] == 1
        assert isinstance(stats["last_auto_decision_at"], str)
        assert events == ["acquire", "release", "acquire", "release"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_run_job_interactive_missing_handle_maps_session_resume_failed(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            }
        )
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
        await local_store.create_request(
            request_id="req-missing-handle",
            skill_id="test-skill",
            engine="codex",
            parameter={},
            engine_options={},
            runtime_options={"execution_mode": "interactive"},
            input_data={},
        )
        await local_store.update_request_run_id("req-missing-handle", run_id)
        await local_store.create_run(run_id, None, "queued")

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": InteractiveAskMissingHandleAdapter()}
        orchestrator.agent_cli_manager.resolve_interactive_profile = lambda engine, session_timeout_sec: EngineInteractiveProfile(
            reason="probe_ok",
            session_timeout_sec=session_timeout_sec,
        )

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill), \
             patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.run_job(
                run_id,
                "test-skill",
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        status_data = _read_state_data(run_dir)
        assert status_data["status"] == "failed"
        assert status_data["error"]["code"] == "SESSION_RESUME_FAILED"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_waiting_user_keeps_waiting_when_handle_valid(tmp_path):
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        await _seed_recovery_run(
            local_store,
            request_id="req-recover-resumable",
            run_id="run-recover-resumable",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"session_timeout_sec": 1200},
            pending={"interaction_id": 1, "kind": "open_text", "prompt": "continue?"},
            session_handle={
                "engine": "codex",
                "handle_type": "session_id",
                "handle_value": "thread-1",
                "created_at_turn": 1,
            },
        )

        orchestrator = JobOrchestrator()
        orchestrator.adapters = {}
        with patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        run_state = await local_store.get_run("run-recover-resumable")
        assert run_state is not None
        assert run_state["status"] == RunStatus.WAITING_USER.value
        recovery = await local_store.get_recovery_info("run-recover-resumable")
        assert recovery["recovery_state"] == "recovered_waiting"
        assert recovery["recovery_reason"] == "resumable_waiting_preserved"
        assert await local_store.get_pending_interaction("req-recover-resumable") is not None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_waiting_user_fails_when_handle_missing(tmp_path):
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        run_dir = await _seed_recovery_run(
            local_store,
            request_id="req-recover-missing-handle",
            run_id="run-recover-missing-handle",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"session_timeout_sec": 1200},
            pending={"interaction_id": 1, "kind": "open_text", "prompt": "continue?"},
        )

        orchestrator = JobOrchestrator()
        with patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        status_data = _read_state_data(run_dir)
        assert status_data["status"] == RunStatus.FAILED.value
        assert status_data["error"]["code"] == "SESSION_RESUME_FAILED"
        run_state = await local_store.get_run("run-recover-missing-handle")
        assert run_state is not None
        assert run_state["status"] == RunStatus.FAILED.value
        recovery = await local_store.get_recovery_info("run-recover-missing-handle")
        assert recovery["recovery_state"] == "failed_reconciled"
        assert await local_store.get_pending_interaction("req-recover-missing-handle") is None
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
        run_dir = await _seed_recovery_run(
            local_store,
            request_id="req-recover-running",
            run_id="run-recover-running",
            status=RunStatus.RUNNING.value,
            runtime_options={"execution_mode": "interactive"},
        )

        orchestrator = JobOrchestrator()
        with patch("server.services.orchestration.job_orchestrator.run_store", local_store):
            await orchestrator.recover_incomplete_runs_on_startup()

        status_data = _read_state_data(run_dir)
        assert status_data["status"] == RunStatus.FAILED.value
        assert status_data["error"]["code"] == "ORCHESTRATOR_RESTART_INTERRUPTED"
        recovery = await local_store.get_recovery_info("run-recover-running")
        assert recovery["recovery_state"] == "failed_reconciled"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_recover_orphan_cleanup_is_noop_and_idempotent(tmp_path):
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
        await _seed_recovery_run(
            local_store,
            request_id="req-recover-idempotent",
            run_id="run-recover-idempotent",
            status=RunStatus.WAITING_USER.value,
            runtime_options={"execution_mode": "interactive"},
            profile={"session_timeout_sec": 1200},
            pending={"interaction_id": 2, "kind": "open_text", "prompt": "continue?"},
        )

        adapter = CountingCancelAdapter()
        orchestrator = JobOrchestrator()
        orchestrator.adapters = {"codex": adapter}
        with patch("server.services.orchestration.job_orchestrator.run_store", local_store):
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


def test_append_orchestrator_event_schema_violation_raises_runtime_error(tmp_path):
    run_dir = tmp_path / "run-schema-error"
    run_dir.mkdir(parents=True, exist_ok=True)
    orchestrator = JobOrchestrator()
    with pytest.raises(RuntimeError, match=InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value):
        orchestrator._append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=1,
            category="lifecycle",
            type_name="lifecycle.run.started",
            data={"status": "queued"},
        )
