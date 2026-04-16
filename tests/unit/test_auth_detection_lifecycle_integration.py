from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from server.config import config
from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
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
        return {
            "auth_signal": {
                "required": True,
                "confidence": "high",
                "subcategory": "oauth_reauth",
                "matched_pattern_id": "codex_refresh_token_reauth_required",
            }
        }

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = live_runtime_emitter
        signal = {
            "required": True,
            "confidence": "high",
            "subcategory": "oauth_reauth",
            "matched_pattern_id": "codex_refresh_token_reauth_required",
        }
        return EngineRunResult(
            exit_code=0,
            raw_stdout="",
            raw_stderr="SERVER_OAUTH2_REQUIRED",
            artifacts_created=[],
            auth_signal_snapshot=signal,
            turn_result=AdapterTurnResult(
                outcome=AdapterTurnOutcome.ASK_USER,
                interaction=AdapterTurnInteraction(
                    interaction_id=1,
                    kind="open_text",
                    prompt="please authenticate",
                ),
            ),
        )


class _LowAuthLoopAdapter:
    def __init__(self, stdout_text: str):
        self.stdout_text = stdout_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {
            "auth_signal": {
                "required": True,
                "confidence": "low",
                "subcategory": None,
                "provider_id": "iflowcn",
                "matched_pattern_id": "opencode_iflowcn_unknown_loop_fallback",
            }
        }

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = live_runtime_emitter
        signal = {
            "required": True,
            "confidence": "low",
            "subcategory": None,
            "provider_id": "iflowcn",
            "matched_pattern_id": "opencode_iflowcn_unknown_loop_fallback",
        }
        return EngineRunResult(
            exit_code=130,
            raw_stdout=self.stdout_text,
            raw_stderr="",
            artifacts_created=[],
            auth_signal_snapshot=signal,
        )


class _CodexHighAuthExitOneAdapter:
    def __init__(self, stdout_text: str):
        self.stdout_text = stdout_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {
            "auth_signal": {
                "required": True,
                "confidence": "high",
                "subcategory": "api_key_missing",
                "matched_pattern_id": "codex_missing_bearer_401",
            }
        }

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
            auth_signal_snapshot={
                "required": True,
                "confidence": "high",
                "subcategory": "api_key_missing",
                "matched_pattern_id": "codex_missing_bearer_401",
            },
        )


class _CodexRefreshReauthExitOneAdapter:
    def __init__(self, stdout_text: str = "", stderr_text: str = ""):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {
            "auth_signal": {
                "required": True,
                "confidence": "high",
                "subcategory": None,
                "matched_pattern_id": "codex_refresh_token_reauth_required",
            }
        }

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
            auth_signal_snapshot={
                "required": True,
                "confidence": "high",
                "subcategory": None,
                "matched_pattern_id": "codex_refresh_token_reauth_required",
            },
        )


class _CodexAccessTokenReauthExitOneAdapter:
    def __init__(self, stdout_text: str = "", stderr_text: str = "", pty_text: str = ""):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.pty_text = pty_text
        self._adapter = CodexExecutionAdapter()
        self.stream_parser = self._adapter.stream_parser

    def parse_runtime_stream(self, **kwargs):
        return self._adapter.parse_runtime_stream(**kwargs)

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        parsed = self.parse_runtime_stream(
            stdout_raw=self.stdout_text.encode("utf-8"),
            stderr_raw=self.stderr_text.encode("utf-8"),
            pty_raw=self.pty_text.encode("utf-8"),
        )
        auth_signal = parsed.get("auth_signal")
        return EngineRunResult(
            exit_code=1,
            raw_stdout=self.stdout_text,
            raw_stderr=self.stderr_text,
            artifacts_created=[],
            auth_signal_snapshot=dict(auth_signal) if isinstance(auth_signal, dict) else None,
        )


class _CodexUsageLimitExitOneAdapter:
    def __init__(self, stdout_text: str = "", stderr_text: str = "", pty_text: str = ""):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.pty_text = pty_text
        self._adapter = CodexExecutionAdapter()
        self.stream_parser = self._adapter.stream_parser

    def parse_runtime_stream(self, **kwargs):
        return self._adapter.parse_runtime_stream(**kwargs)

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        parsed = self.parse_runtime_stream(
            stdout_raw=self.stdout_text.encode("utf-8"),
            stderr_raw=self.stderr_text.encode("utf-8"),
            pty_raw=self.pty_text.encode("utf-8"),
        )
        auth_signal = parsed.get("auth_signal")
        return EngineRunResult(
            exit_code=1,
            raw_stdout=self.stdout_text,
            raw_stderr=self.stderr_text,
            artifacts_created=[],
            auth_signal_snapshot=dict(auth_signal) if isinstance(auth_signal, dict) else None,
        )


class _ExitOneAdapter:
    def __init__(
        self,
        stdout_text: str = "",
        stderr_text: str = "",
        auth_signal: dict[str, object] | None = None,
    ):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.auth_signal = auth_signal
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        if isinstance(self.auth_signal, dict):
            return {"auth_signal": dict(self.auth_signal)}
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
            auth_signal_snapshot=dict(self.auth_signal) if isinstance(self.auth_signal, dict) else None,
        )


class _LowConfidenceAttributedAuthAdapter:
    def __init__(self, stdout_text: str = "", stderr_text: str = ""):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.stream_parser = object()

    def parse_runtime_stream(self, **_kwargs):
        return {
            "auth_signal": {
                "required": True,
                "confidence": "low",
                "subcategory": None,
                "matched_pattern_id": "generic_token_expired_text_fallback",
            }
        }

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        return EngineRunResult(
            exit_code=143,
            raw_stdout=self.stdout_text,
            raw_stderr=self.stderr_text,
            artifacts_created=[],
            failure_reason="AUTH_REQUIRED",
            auth_signal_snapshot={
                "required": True,
                "confidence": "low",
                "subcategory": None,
                "matched_pattern_id": "generic_token_expired_text_fallback",
            },
        )


class _QwenOAuthWaitingAdapter:
    def __init__(self, stderr_text: str):
        self.stderr_text = stderr_text
        self._adapter = QwenExecutionAdapter()
        self.stream_parser = self._adapter.stream_parser

    def parse_runtime_stream(self, **kwargs):
        return self._adapter.parse_runtime_stream(**kwargs)

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        parsed = self.parse_runtime_stream(
            stdout_raw=b"",
            stderr_raw=self.stderr_text.encode("utf-8"),
            pty_raw=b"",
        )
        auth_signal = parsed.get("auth_signal")
        return EngineRunResult(
            exit_code=130,
            raw_stdout="",
            raw_stderr=self.stderr_text,
            artifacts_created=[],
            failure_reason="AUTH_REQUIRED",
            auth_signal_snapshot=dict(auth_signal) if isinstance(auth_signal, dict) else None,
        )


class _ClaudeLoginPromptAdapter:
    def __init__(self, stdout_text: str):
        self.stdout_text = stdout_text
        self._adapter = ClaudeExecutionAdapter()
        self.stream_parser = self._adapter.stream_parser

    def parse_runtime_stream(self, **kwargs):
        return self._adapter.parse_runtime_stream(**kwargs)

    async def run(self, skill, input_data, run_dir: Path, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = options
        _ = live_runtime_emitter
        parsed = self.parse_runtime_stream(
            stdout_raw=self.stdout_text.encode("utf-8"),
            stderr_raw=b"",
            pty_raw=b"",
        )
        auth_signal = parsed.get("auth_signal")
        return EngineRunResult(
            exit_code=1,
            raw_stdout=self.stdout_text,
            raw_stderr="",
            artifacts_created=[],
            failure_reason="AUTH_REQUIRED",
            auth_signal_snapshot=dict(auth_signal) if isinstance(auth_signal, dict) else None,
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
) -> JobOrchestrator:
    orchestrator = JobOrchestrator(
        OrchestratorDeps(
            run_store_backend=local_store,
            concurrency_backend=_NoopConcurrencyManager(),
            trust_manager_backend=_NoopTrustManager(),
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-skill", engine="codex")
        run_id = _create_run(skill, "codex")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-high",
            run_id=run_id,
            skill_id=skill.id,
            engine="codex",
        )
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {"codex": _HighAuthInteractiveAdapter()}

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
async def test_low_confidence_auth_detection_is_audited_without_forcing_waiting_auth(
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
            request_id="req-auth-low",
            run_id=run_id,
            skill_id=skill.id,
            engine="opencode",
        )
        fixture = load_sample("opencode", "iflowcn_unknown_step_finish_loop")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "opencode": _LowAuthLoopAdapter(stdout_text=fixture["stdout"])
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
        assert meta_data["auth_detection"]["subcategory"] is None
        assert meta_data["auth_detection"]["confidence"] == "low"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_low_confidence_auth_signal_does_not_translate_terminal_failure_to_auth_required(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-low-terminal", engine="opencode")
        run_id = _create_run(skill, "opencode")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-low-terminal",
            run_id=run_id,
            skill_id=skill.id,
            engine="opencode",
        )
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "opencode": _LowConfidenceAttributedAuthAdapter(
                stdout_text="The citation_scope.json file isn't being created.",
            )
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
        assert result_data["status"] == "failed"
        assert result_data["error"]["code"] is None
        assert result_data["error"]["message"] == "Exit code 143"
        assert meta_data["process"]["failure_reason"] is None
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "low"
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
        methods = pending_selection["available_methods"]
        assert "callback" in methods
        assert "device_auth" in methods
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
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "opencode": _ExitOneAdapter(
                auth_signal={
                    "required": True,
                    "confidence": "high",
                    "subcategory": "api_key_missing",
                    "matched_pattern_id": "opencode_deepseek_api_key_missing",
                }
            )
        }

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
async def test_codex_refresh_token_reauth_high_confidence_enters_waiting_auth(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-codex-refresh-reauth", engine="codex")
        run_id = _create_run(skill, "codex")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-codex-refresh-reauth",
            run_id=run_id,
            skill_id=skill.id,
            engine="codex",
        )
        fixture = load_sample("codex", "openai_refresh_token_reused_401")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "codex": _CodexRefreshReauthExitOneAdapter(
                stdout_text=fixture["stdout"],
                stderr_text=fixture["stderr"],
            )
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
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        pending_selection = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert "callback" in pending_selection["available_methods"]
        assert "device_auth" in pending_selection["available_methods"]
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_codex_logged_out_access_token_reauth_high_confidence_enters_waiting_auth(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-codex-access-token-reauth", engine="codex")
        run_id = _create_run(skill, "codex")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-codex-access-token-reauth",
            run_id=run_id,
            skill_id=skill.id,
            engine="codex",
        )
        fixture = load_sample("codex", "openai_access_token_logged_out_401")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "codex": _CodexAccessTokenReauthExitOneAdapter(
                stdout_text=fixture["stdout"],
                stderr_text=fixture["stderr"],
                pty_text=fixture["pty_output"],
            )
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
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        pending_selection = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert "callback" in pending_selection["available_methods"]
        assert "device_auth" in pending_selection["available_methods"]
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
        assert "codex_access_token_reauth_required" in meta_data["auth_detection"]["matched_rule_ids"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_codex_usage_limit_high_confidence_enters_waiting_auth_and_preserves_reason(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-codex-usage-limit", engine="codex")
        run_id = _create_run(skill, "codex")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-codex-usage-limit",
            run_id=run_id,
            skill_id=skill.id,
            engine="codex",
        )
        fixture = load_sample("codex", "openai_usage_limit_plus")
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "codex": _CodexUsageLimitExitOneAdapter(
                stdout_text=fixture["stdout"],
                stderr_text=fixture["stderr"],
                pty_text=fixture["pty_output"],
            )
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
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        pending_selection = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert "usage limit" in str(pending_selection.get("last_error", "")).lower()
        assert "usage limit" in str(pending_selection.get("instructions", "")).lower()
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
        assert "codex_usage_limit_plus_reauth_required" in meta_data["auth_detection"]["matched_rule_ids"]
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_qwen_oauth_waiting_banner_enters_waiting_auth_without_protocol_schema_failure(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-qwen-oauth", engine="qwen")
        run_id = _create_run(skill, "qwen")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-qwen-oauth",
            run_id=run_id,
            skill_id=skill.id,
            engine="qwen",
            engine_options={"model": "coder-model"},
        )
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "qwen": _QwenOAuthWaitingAdapter(
                stderr_text=(
                    "Qwen OAuth Device Authorization\n"
                    "https://chat.qwen.ai/authorize?user_code=TEST-123\n"
                    "Waiting for authorization to complete...\n"
                )
            )
        }

        with patch(
            "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.start_session",
            lambda **_kwargs: {
                "session_id": "auth-qwen-1",
                "engine": "qwen",
                "provider_id": "qwen-oauth",
                "status": "waiting_user",
                "input_kind": None,
                "auth_url": "https://chat.qwen.ai/authorize?user_code=TEST-123",
                "user_code": "TEST-123",
                "created_at": "2099-03-03T00:00:00Z",
                "expires_at": "2099-03-03T00:15:00Z",
                "error": None,
            },
        ), patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "qwen",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        state_data = _read_state_data(run_dir)
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        pending_auth = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.challenge_active"
        assert pending_auth["provider_id"] == "qwen-oauth"
        assert pending_auth["auth_url"] == "https://chat.qwen.ai/authorize?user_code=TEST-123"
        assert pending_auth["user_code"] == "TEST-123"
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
        assert meta_data["auth_detection"]["provider_id"] is None
        assert meta_data["auth_session"]["status"] == "waiting"
        assert meta_data["auth_session"]["provider_id"] == "qwen-oauth"
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()


@pytest.mark.asyncio
async def test_claude_not_logged_in_login_prompt_enters_waiting_auth(
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
        skill = _build_interactive_skill(tmp_path, skill_id="auth-claude-login-prompt", engine="claude")
        run_id = _create_run(skill, "claude")
        await _seed_interactive_request(
            local_store,
            request_id="req-auth-claude-login-prompt",
            run_id=run_id,
            skill_id=skill.id,
            engine="claude",
        )
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "claude": _ClaudeLoginPromptAdapter(
                stdout_text=(
                    '{"type":"system","subtype":"init","session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa"}\n'
                    '{"type":"assistant","message":{"id":"6855d0ed-b48c-4fab-8311-cb2549387d8b","content":[{"type":"text","text":"Not logged in \\u00b7 Please run /login"}]},"session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa","error":"authentication_failed"}\n'
                    '{"type":"result","subtype":"success","is_error":true,"session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa","result":"Not logged in \\u00b7 Please run /login"}\n'
                )
            )
        }

        with patch("server.services.skill.skill_registry.skill_registry.get_skill", return_value=skill):
            await orchestrator.run_job(
                run_id,
                skill.id,
                "claude",
                options={"execution_mode": "interactive"},
            )

        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        state_data = _read_state_data(run_dir)
        meta_data = json.loads((run_dir / ".audit" / "meta.1.json").read_text(encoding="utf-8"))
        pending_selection = state_data["pending"]["payload"]
        assert state_data["status"] == RunStatus.WAITING_AUTH.value
        assert state_data["error"] is None
        assert state_data["pending"]["owner"] == "waiting_auth.method_selection"
        assert "callback" in pending_selection["available_methods"]
        assert "auth_code_or_url" in pending_selection["available_methods"]
        assert "custom_provider" not in pending_selection["available_methods"]
        assert meta_data["auth_detection"]["classification"] == "auth_required"
        assert meta_data["auth_detection"]["confidence"] == "high"
        assert meta_data["auth_detection"]["matched_rule_ids"] == ["claude_not_logged_in"]
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
        orchestrator = _build_orchestrator(local_store)
        orchestrator.adapters = {
            "opencode": _ExitOneAdapter(
                auth_signal={
                    "required": True,
                    "confidence": "high",
                    "subcategory": "api_key_missing",
                    "matched_pattern_id": "opencode_deepseek_api_key_missing",
                }
            )
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
