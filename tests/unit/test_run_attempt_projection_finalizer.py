from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from server.models import PendingOwner, RunStatus
from server.runtime.auth_detection.types import AuthDetectionResult
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionResult,
)
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptResolvedOutcome,
)
from server.services.orchestration.run_attempt_preparation_service import RunAttemptContext
from server.services.orchestration.run_attempt_projection_finalizer import (
    RunAttemptFinalizeInput,
    RunAttemptProjectionFinalizer,
)
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


class _ProjectionRecorder:
    def __init__(self) -> None:
        self.non_terminal_calls: list[dict[str, Any]] = []
        self.terminal_calls: list[dict[str, Any]] = []

    async def write_non_terminal_projection(self, **kwargs: Any) -> None:
        self.non_terminal_calls.append(kwargs)

    async def write_terminal_projection(self, **kwargs: Any) -> None:
        self.terminal_calls.append(kwargs)


class _RunStoreRecorder:
    def __init__(self) -> None:
        self.status_updates: list[tuple[str, RunStatus, str | None]] = []
        self.cache_entries: list[tuple[str, str]] = []
        self.temp_cache_entries: list[tuple[str, str]] = []

    async def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        result_path: str | None = None,
    ) -> None:
        self.status_updates.append((run_id, status, result_path))

    async def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        self.cache_entries.append((cache_key, run_id))

    async def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        self.temp_cache_entries.append((cache_key, run_id))


@dataclass
class _BundleRecorder:
    calls: list[tuple[Path, bool]]

    def __call__(self, run_dir: Path, debug: bool) -> str:
        self.calls.append((run_dir, debug))
        suffix = "debug" if debug else "normal"
        return str(run_dir / f"bundle-{suffix}.zip")


class _AuditStub:
    pass


def _build_context(tmp_path: Path) -> RunAttemptContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunAttemptContext(
        request=RunJobRequest(
            run_id="run-1",
            skill_id="skill-1",
            engine_name="codex",
            options={"execution_mode": "auto"},
        ),
        run_dir=run_dir,
        request_record={"request_id": "req-1"},
        request_id="req-1",
        execution_mode="auto",
        conversation_mode="session",
        session_capable=True,
        is_interactive=True,
        interactive_auto_reply=False,
        can_wait_for_user=True,
        can_persist_waiting_user=True,
        interactive_profile=None,
        attempt_number=1,
        skill=object(),
        adapter=None,
        input_data={"input": {}, "parameter": {}},
        run_options={"__run_id": "run-1"},
        custom_provider_model=None,
    )


def _build_execution() -> RunAttemptExecutionResult:
    async def _consume(_handle_id: str) -> dict[str, Any]:
        return {"status": "stored"}

    return RunAttemptExecutionResult(
        engine_result=None,
        process_exit_code=0,
        process_failure_reason=None,
        process_raw_stdout="stdout",
        process_raw_stderr="stderr",
        runtime_execution_warnings=[],
        adapter_stream_parser=None,
        auth_signal_snapshot=None,
        run_handle_consumer=_consume,
        live_runtime_emitter_factory=lambda: None,
    )


def _build_auth_detection() -> AuthDetectionResult:
    return AuthDetectionResult(
        classification="unknown",
        subcategory=None,
        confidence="low",
        engine="codex",
        evidence_sources=[],
        details={},
    )


def _build_outcome(
    *,
    status: RunStatus,
    pending_interaction: dict[str, Any] | None = None,
    pending_auth: dict[str, Any] | None = None,
    pending_auth_method_selection: dict[str, Any] | None = None,
    normalized_error: dict[str, Any] | None = None,
    final_error_code: str | None = None,
    terminal_error_summary: str | None = None,
) -> RunAttemptResolvedOutcome:
    success_source = "structured_output_candidate" if status == RunStatus.SUCCEEDED else None
    return RunAttemptResolvedOutcome(
        final_status=status,
        normalized_error=normalized_error,
        warnings=["WARN_A"],
        output_data={"answer": 42},
        success_source=success_source,
        artifacts=["artifacts/out.txt"],
        repair_level="deterministic_generic",
        pending_interaction=pending_interaction,
        pending_auth=pending_auth,
        pending_auth_method_selection=pending_auth_method_selection,
        auth_session_meta={"session_id": "auth-1"} if pending_auth is not None else None,
        turn_payload_for_completion={"answer": 42},
        process_exit_code=0,
        process_failure_reason=None,
        process_raw_stdout="stdout",
        process_raw_stderr="stderr",
        auth_detection_result=_build_auth_detection(),
        auth_signal_snapshot=None,
        runtime_parse_result=None,
        terminal_error_summary=terminal_error_summary,
        final_error_code=final_error_code,
        effective_session_timeout_sec=123,
        auto_resume_requested=False,
    )


def _build_finalize_input(
    tmp_path: Path,
    *,
    outcome: RunAttemptResolvedOutcome,
    request_record: dict[str, Any] | None = None,
    cache_key: str | None = None,
) -> tuple[RunAttemptFinalizeInput, _ProjectionRecorder, _RunStoreRecorder, list[dict[str, Any]], _BundleRecorder]:
    context = _build_context(tmp_path)
    projection = _ProjectionRecorder()
    run_store = _RunStoreRecorder()
    events: list[dict[str, Any]] = []
    bundles = _BundleRecorder(calls=[])

    finalize_input = RunAttemptFinalizeInput(
        context=context,
        execution=_build_execution(),
        outcome=outcome,
        request_record=request_record if request_record is not None else {"skill_source": "installed"},
        run_id="run-1",
        request_id="req-1",
        cache_key=cache_key,
        attempt_started_at=datetime(2026, 4, 16, 10, 0, 0),
        fs_before_snapshot={},
        run_store_backend=run_store,
        run_projection_service=projection,
        audit_service=SimpleNamespace(append_orchestrator_event=lambda **kwargs: events.append(kwargs)),
        build_run_bundle=bundles,
        summarize_terminal_error_message=lambda value: str(value) if value else None,
        execution_mode="interactive",
        options={"execution_mode": "interactive"},
        adapter=None,
    )
    return finalize_input, projection, run_store, events, bundles


@pytest.mark.asyncio
async def test_projection_finalizer_writes_waiting_user_projection(tmp_path: Path) -> None:
    outcome = _build_outcome(
        status=RunStatus.WAITING_USER,
        pending_interaction={"interaction_id": 7, "message": "Need input"},
    )
    finalize_input, projection, run_store, events, bundles = _build_finalize_input(
        tmp_path,
        outcome=outcome,
    )

    result = await RunAttemptProjectionFinalizer().finalize(inputs=finalize_input)

    assert result.final_status == RunStatus.WAITING_USER
    assert len(projection.non_terminal_calls) == 1
    assert projection.non_terminal_calls[0]["pending_owner"] == PendingOwner.WAITING_USER
    assert run_store.status_updates == [("run-1", RunStatus.WAITING_USER, None)]
    assert events == []
    assert bundles.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload_key", "expected_owner"),
    [
        ("pending_auth_method_selection", PendingOwner.WAITING_AUTH_METHOD_SELECTION),
        ("pending_auth", PendingOwner.WAITING_AUTH_CHALLENGE),
    ],
)
async def test_projection_finalizer_writes_waiting_auth_projection(
    tmp_path: Path,
    payload_key: str,
    expected_owner: PendingOwner,
) -> None:
    kwargs: dict[str, dict[str, Any] | None] = {
        "pending_auth_method_selection": None,
        "pending_auth": None,
    }
    kwargs[payload_key] = {"auth_session_id": "sess-1"}
    outcome = _build_outcome(
        status=RunStatus.WAITING_AUTH,
        pending_auth_method_selection=kwargs["pending_auth_method_selection"],
        pending_auth=kwargs["pending_auth"],
    )
    finalize_input, projection, run_store, _events, _bundles = _build_finalize_input(
        tmp_path,
        outcome=outcome,
    )

    await RunAttemptProjectionFinalizer().finalize(inputs=finalize_input)

    assert len(projection.non_terminal_calls) == 1
    assert projection.non_terminal_calls[0]["pending_owner"] == expected_owner
    assert run_store.status_updates == [("run-1", RunStatus.WAITING_AUTH, None)]


@pytest.mark.asyncio
async def test_projection_finalizer_writes_success_terminal_bundle_and_cache(tmp_path: Path) -> None:
    outcome = _build_outcome(status=RunStatus.SUCCEEDED)
    finalize_input, projection, run_store, events, bundles = _build_finalize_input(
        tmp_path,
        outcome=outcome,
        cache_key="cache-1",
    )

    result = await RunAttemptProjectionFinalizer().finalize(inputs=finalize_input)

    assert len(projection.terminal_calls) == 1
    assert result.result_path == finalize_input.context.run_dir / "result" / "result.json"
    assert run_store.status_updates == [("run-1", RunStatus.SUCCEEDED, str(result.result_path))]
    assert bundles.calls == [
        (finalize_input.context.run_dir, False),
        (finalize_input.context.run_dir, True),
    ]
    assert run_store.cache_entries == [("cache-1", "run-1")]
    assert run_store.temp_cache_entries == []
    assert len(events) == 1
    assert events[0]["type_name"] == "lifecycle.run.terminal"
    assert events[0]["data"] == {
        "status": "succeeded",
        "completion_source": "structured_output_candidate",
    }


@pytest.mark.asyncio
async def test_projection_finalizer_writes_failed_terminal_event_with_code_and_message(
    tmp_path: Path,
) -> None:
    outcome = _build_outcome(
        status=RunStatus.FAILED,
        normalized_error={"code": "FAILED_CODE", "message": "Something broke"},
        final_error_code="FAILED_CODE",
        terminal_error_summary="Something broke",
    )
    finalize_input, projection, run_store, events, bundles = _build_finalize_input(
        tmp_path,
        outcome=outcome,
    )

    await RunAttemptProjectionFinalizer().finalize(inputs=finalize_input)

    assert len(projection.terminal_calls) == 1
    assert projection.terminal_calls[0]["terminal_result"]["error"] == {
        "code": "FAILED_CODE",
        "message": "Something broke",
    }
    assert run_store.status_updates == [
        ("run-1", RunStatus.FAILED, str(finalize_input.context.run_dir / "result" / "result.json"))
    ]
    assert bundles.calls == []
    assert len(events) == 1
    assert events[0]["data"] == {
        "status": "failed",
        "code": "FAILED_CODE",
        "message": "Something broke",
    }


@pytest.mark.asyncio
async def test_projection_finalizer_keeps_canceled_event_semantics(tmp_path: Path) -> None:
    outcome = _build_outcome(
        status=RunStatus.CANCELED,
        normalized_error={"code": "CANCELED_BY_USER", "message": "Canceled by user request"},
        final_error_code="CANCELED_BY_USER",
        terminal_error_summary="Canceled by user request",
    )
    finalize_input, projection, run_store, events, _bundles = _build_finalize_input(
        tmp_path,
        outcome=outcome,
    )

    await RunAttemptProjectionFinalizer().finalize(
        inputs=finalize_input,
        terminal_event_type_name="lifecycle.run.canceled",
        failure_error_type="RunCanceled",
    )

    assert len(projection.terminal_calls) == 1
    assert run_store.status_updates == [
        ("run-1", RunStatus.CANCELED, str(finalize_input.context.run_dir / "result" / "result.json"))
    ]
    assert len(events) == 1
    assert events[0]["type_name"] == "lifecycle.run.canceled"
    assert events[0]["data"] == {"status": "canceled"}
