from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from server.config import config
from server.models import (
    AdapterTurnInteraction,
    AdapterTurnOutcome,
    AdapterTurnResult,
    EngineInteractiveProfile,
    ExecutionMode,
    RunCreateRequest,
    RunStatus,
    SkillManifest,
)
from server.runtime.auth_detection.types import AuthDetectionResult
from server.runtime.adapter.types import EngineRunResult
from server.services.orchestration.job_orchestrator import JobOrchestrator, OrchestratorDeps
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.workspace_manager import workspace_manager
from tests.unit.auth_detection_test_utils import load_sample


class _NoopConcurrencyManager:
    async def acquire_slot(self) -> None:
        return None

    async def release_slot(self) -> None:
        return None


class _NoopTrustManager:
    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        return None

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        return None


class _HighAuthInteractiveAdapter:
    stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {}

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = live_runtime_emitter
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="SERVER_OAUTH2_REQUIRED",
            artifacts_created=[],
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.ASK_USER,
                interaction=AdapterTurnInteraction(
                    interaction_id=1,
                    kind="open_text",
                    prompt="please authenticate",
                ),
            ),
        )


class _MediumAuthLoopAdapter:
    def __init__(self, stdout_text: str):
        self.stdout_text = stdout_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {}

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = live_runtime_emitter
        return EngineRunResult(
            exit_code=130,
            raw_stdout=self.stdout_text,
            raw_stderr="",
            artifacts_created=[],
        )


class _CodexHighAuthExitOneAdapter:
    def __init__(self, stdout_text: str):
        self.stdout_text = stdout_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {}

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        return EngineRunResult(
            exit_code=1,
            raw_stdout=self.stdout_text,
            raw_stderr="",
            artifacts_created=[],
        )


class _ExitOneAdapter:
    def __init__(self, stdout_text: str = "", stderr_text: str = ""):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {}

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        return EngineRunResult(
            exit_code=1,
            raw_stdout=self.stdout_text,
            raw_stderr=self.stderr_text,
            artifacts_created=[],
        )


def _build_interactive_skill(tmp_path: Path, *, skill_id: str, engine: str) -> SkillManifest:
    skill_dir = tmp_path / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (skill_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        engines=[engine],
        execution_modes=[ExecutionMode.INTERACTIVE],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
    )


def _create_run(skill: SkillManifest, engine: str) -> str:
    with patch(
        "server.services.skill.skill_registry.skill_registry.get_skill",
        return_value=skill,
    ):
        response = workspace_manager.create_run(
            RunCreateRequest(skill_id=skill.id, engine=engine, parameter={})
        )
    return response.run_id


def _read_state_data(run_dir: Path) -> dict:
    return json.loads((run_dir / ".state" / "state.json").read_text(encoding="utf-8"))


async def _seed_interactive_request(
    store: RunStore,
    *,
    request_id: str,
    run_id: str,
    skill_id: str,
    engine: str,
    engine_options: dict[str, object] | None = None,
) -> None:
    await store.create_request(
        request_id=request_id,
        skill_id=skill_id,
        engine=engine,
        parameter={},
        engine_options=engine_options or {},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    await store.update_request_run_id(request_id, run_id)
    await store.create_run(run_id, None, "queued")


def _build_orchestrator(
    local_store: RunStore,
    *,
    auth_detection_service: object | None = None,
) -> JobOrchestrator:
    orchestrator = JobOrchestrator(
        OrchestratorDeps(
            run_store_backend=local_store,
            concurrency_backend=_NoopConcurrencyManager(),
            trust_manager_backend=_NoopTrustManager(),
            auth_detection_service=auth_detection_service,
        )
    )
    orchestrator.agent_cli_manager.resolve_interactive_profile = (
        lambda engine, session_timeout_sec: EngineInteractiveProfile(
            mode="cli_delegate",
            session_timeout_sec=session_timeout_sec,
        )
    )
    return orchestrator


@pytest.mark.asyncio
async def test_high_confidence_auth_detection_overrides_waiting_user(tmp_path: Path) -> None:
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        skill = _build_interactive_skill(tmp_path, skill_id="auth-skill", engine="iflow")
        run_id = _create_run(skill, "iflow")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-high",
            run_id=run_id,
            skill_id=skill.id,
            engine="iflow",
        )
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {"iflow": _HighAuthInteractiveAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "iflow",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        state_data = _read_state_data(run_dir)
        pending_selection = state_data["pending"]["payload"]
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert state_data["pending"]["interaction_id"] is None
        assert state_data["pending"]["auth_session_id"] is None
        assert pending_selection["phase"] == "method_selection"
        assert pending_selection["available_methods"]
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
        assert meta_data["auth_session"]["status"] == "none"
        assert meta_data["auth_session"]["challenge_kind"] is None
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_medium_confidence_auth_detection_is_audited_without_forcing_auth_required(
    tmp_path: Path,
) -> None:
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        skill = _build_interactive_skill(tmp_path, skill_id="auth-loop-skill", engine="opencode")
        run_id = _create_run(skill, "opencode")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-medium",
            run_id=run_id,
            skill_id=skill.id,
            engine="opencode",
        )
        fixture = load_sample("opencode", "iflowcn_unknown_step_finish_loop")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "opencode": _MediumAuthLoopAdapter(stdout_text=fixture["stdout"])
        }

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "opencode",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text(encoding="utf-8"))
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        assert result_data["error"]["code"] is None
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["subcategory"] == "unknown_auth"
        assert meta_data["auth_detection"]["confidence"] == "medium"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_high_confidence_auth_detection_with_selection_survives_nonzero_exit(
    tmp_path: Path,
) -> None:
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        skill = _build_interactive_skill(tmp_path, skill_id="auth-codex-skill", engine="codex")
        run_id = _create_run(skill, "codex")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-codex-selection",
            run_id=run_id,
            skill_id=skill.id,
            engine="codex",
        )
        fixture = load_sample("codex", "openai_missing_bearer_401")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "codex": _CodexHighAuthExitOneAdapter(stdout_text=fixture["stdout"])
        }

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "codex",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        state_data = _read_state_data(run_dir)
        pending_selection = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert pending_selection["available_methods"] == ["callback", "device_auth"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_opencode_high_confidence_auth_with_null_detection_provider_uses_model_prefix_for_waiting_auth(
    tmp_path: Path,
) -> None:
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        skill = _build_interactive_skill(
            tmp_path,
            skill_id="auth-opencode-fallback",
            engine="opencode",
        )
        run_id = _create_run(skill, "opencode")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-opencode-fallback",
            run_id=run_id,
            skill_id=skill.id,
            engine="opencode",
            engine_options={"model": "deepseek/deepseek-reasoner"},
        )
        orchestrator = _build_orchestrator(
            local_store,
            auth_detection_service=SimpleNamespace(
                detect=lambda **_kwargs: AuthDetectionResult(
                    classification="auth_required",
                    subcategory="api_key_missing",
                    confidence="high",
                    engine="opencode",
                    provider_id=None,
                    matched_rule_ids=["opencode_deepseek_api_key_missing"],
                    evidence_sources=["structured_ndjson"],
                    evidence_excerpt="API key is missing",
                    details={},
                )
            ),
        )
        orchestrator.adapters = {"opencode": _ExitOneAdapter()}

        with patch(
            "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.start_session",
            lambda **_kwargs: {
                "session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "deepseek",
                "status": "waiting_user",
                "input_kind": "api_key",
                "auth_url": None,
                "user_code": None,
                "created_at": "2099-03-03T00:00:00Z",
                "expires_at": "2099-03-03T00:15:00Z",
                "error": None,
            },
        ), patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "opencode",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        state_data = _read_state_data(run_dir)
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["pending"]["payload"]["provider_id"] == "deepseek"
        assert meta_data["auth_detection"]["provider_id"] is None
        assert meta_data["auth_session"]["provider_id"] == "deepseek"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_opencode_high_confidence_auth_with_unresolved_model_audits_reason_and_fails(
    tmp_path: Path,
) -> None:
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()
    try:
        local_store = RunStore(db_path=tmp_path / "runs.db")
        skill = _build_interactive_skill(
            tmp_path,
            skill_id="auth-opencode-unresolved",
            engine="opencode",
        )
        run_id = _create_run(skill, "opencode")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-opencode-unresolved",
            run_id=run_id,
            skill_id=skill.id,
            engine="opencode",
            engine_options={"model": "deepseek"},
        )
        orchestrator = _build_orchestrator(
            local_store,
            auth_detection_service=SimpleNamespace(
                detect=lambda **_kwargs: AuthDetectionResult(
                    classification="auth_required",
                    subcategory="api_key_missing",
                    confidence="high",
                    engine="opencode",
                    provider_id=None,
                    matched_rule_ids=["opencode_deepseek_api_key_missing"],
                    evidence_sources=["structured_ndjson"],
                    evidence_excerpt="API key is missing",
                    details={},
                )
            ),
        )
        orchestrator.adapters = {"opencode": _ExitOneAdapter()}

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "opencode",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        result_data = json.loads((run_dir / "result" / "result.json").read_text(encoding="utf-8"))
        audit_rows = [
            json.loads(line)
            for line in (run_dir / ".audit" / "orchestrator_events.1.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        warning = next(row for row in audit_rows if row["type"] == "diagnostic.warning")
        assert result_data["error"]["code"] == "AUTH_REQUIRED"
        assert "OPENCODE_PROVIDER_UNRESOLVED_FROM_MODEL" in result_data["validation_warnings"]
        assert warning["data"]["code"] == "OPENCODE_PROVIDER_UNRESOLVED_FROM_MODEL"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()
