from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from server.models import EngineInteractiveProfile, RunStatus
from server.services.orchestration.job_orchestrator import JobOrchestrator
from server.services.orchestration.run_store import RunStore
from server.config import config
from tests.unit.test_job_orchestrator import (
    InteractiveAskMissingHandleAdapter,
    InteractiveTwoTurnAdapter,
    _build_interactive_skill,
    _create_run_with_skill,
    _read_state_data,
    _seed_interactive_request,
    _seed_recovery_run,
)


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
            request_id="req-missing-handle",
            skill_id=skill.id,
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
                skill.id,
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
