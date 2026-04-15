from __future__ import annotations

from typing import Any

import pytest

from server.services.orchestration.job_orchestrator import JobOrchestrator, OrchestratorDeps
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


class _RecordingLifecycleService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, RunJobRequest]] = []

    async def run(self, *, orchestrator: Any, request: RunJobRequest) -> None:
        self.calls.append((orchestrator, request))


class _RecordingRecoveryService:
    def __init__(self) -> None:
        self.calls = 0

    async def recover_incomplete_runs_on_startup(self, **_kwargs: Any) -> None:
        self.calls += 1


def test_job_orchestrator_exposes_stable_facade_entrypoints() -> None:
    orchestrator = JobOrchestrator()

    assert callable(orchestrator.run_job)
    assert callable(orchestrator.cancel_run)
    assert callable(orchestrator.recover_incomplete_runs_on_startup)
    assert callable(orchestrator.build_run_bundle)


@pytest.mark.asyncio
async def test_run_job_delegates_to_lifecycle_service_via_run_job_request() -> None:
    lifecycle = _RecordingLifecycleService()
    orchestrator = JobOrchestrator(
        deps=OrchestratorDeps(
            run_job_lifecycle_service=lifecycle,
            adapters={},
        )
    )

    options = {"execution_mode": "auto", "model": "test-model"}
    await orchestrator.run_job(
        "run-1",
        "skill-1",
        "codex",
        options,
        cache_key="cache-1",
        temp_request_id="temp-1",
    )

    assert len(lifecycle.calls) == 1
    delegated_orchestrator, request = lifecycle.calls[0]
    assert delegated_orchestrator is orchestrator
    assert request == RunJobRequest(
        run_id="run-1",
        skill_id="skill-1",
        engine_name="codex",
        options=options,
        cache_key="cache-1",
        temp_request_id="temp-1",
    )


@pytest.mark.asyncio
async def test_recover_incomplete_runs_on_startup_delegates_to_recovery_service() -> None:
    recovery = _RecordingRecoveryService()
    orchestrator = JobOrchestrator(
        deps=OrchestratorDeps(
            recovery_service=recovery,
            adapters={},
        )
    )

    await orchestrator.recover_incomplete_runs_on_startup()

    assert recovery.calls == 1
