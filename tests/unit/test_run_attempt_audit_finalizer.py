from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from server.models import RunStatus
from server.runtime.auth_detection.types import AuthDetectionResult
from server.services.orchestration.run_attempt_audit_finalizer import (
    RunAttemptAuditFinalizer,
)
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionResult,
)
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptResolvedOutcome,
)
from server.services.orchestration.run_attempt_preparation_service import RunAttemptContext
from server.services.orchestration.run_attempt_projection_finalizer import (
    RunAttemptFinalizeInput,
)
from server.services.orchestration.run_audit_service import RunAuditService
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


class _ProjectionStub:
    async def write_non_terminal_projection(self, **_kwargs: Any) -> None:
        return None

    async def write_terminal_projection(self, **_kwargs: Any) -> None:
        return None


class _RunStoreStub:
    async def update_run_status(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FailingAuditService:
    def write_attempt_audit_artifacts(self, **_kwargs: Any) -> None:
        raise OSError("disk full")


def _build_context(tmp_path: Path) -> RunAttemptContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunAttemptContext(
        request=RunJobRequest(
            run_id="run-1",
            skill_id="skill-1",
            engine_name="codex",
            options={"execution_mode": "interactive"},
        ),
        run_dir=run_dir,
        request_record={"request_id": "req-1"},
        request_id="req-1",
        execution_mode="interactive",
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


def _build_outcome() -> RunAttemptResolvedOutcome:
    return RunAttemptResolvedOutcome(
        final_status=RunStatus.SUCCEEDED,
        normalized_error=None,
        warnings=["WARN_A"],
        output_data={"answer": 42},
        success_source="structured_output_candidate",
        artifacts=[],
        repair_level="none",
        pending_interaction=None,
        pending_auth=None,
        pending_auth_method_selection=None,
        auth_session_meta={
            "session_id": "auth-1",
            "engine": "codex",
            "provider_id": "openai",
            "challenge_kind": "browser",
            "status": "waiting",
            "source_attempt": 1,
            "resume_attempt": None,
            "last_error": None,
            "redacted_submission": {"kind": None, "present": False},
        },
        turn_payload_for_completion={"answer": 42},
        process_exit_code=0,
        process_failure_reason=None,
        process_raw_stdout="stdout",
        process_raw_stderr="stderr",
        auth_detection_result=AuthDetectionResult(
            classification="auth_required",
            subcategory="challenge",
            confidence="high",
            engine="codex",
            provider_id="openai",
            evidence_sources=["stderr"],
            details={"reason_code": "LOGIN_REQUIRED"},
        ),
        auth_signal_snapshot=None,
        runtime_parse_result=None,
        terminal_error_summary=None,
        final_error_code=None,
        effective_session_timeout_sec=180,
        auto_resume_requested=False,
    )


def _build_finalize_input(tmp_path: Path, *, audit_service: Any) -> RunAttemptFinalizeInput:
    context = _build_context(tmp_path)

    return RunAttemptFinalizeInput(
        context=context,
        execution=_build_execution(),
        outcome=_build_outcome(),
        request_record={"skill_source": "installed"},
        run_id="run-1",
        request_id="req-1",
        cache_key=None,
        attempt_started_at=datetime(2026, 4, 16, 10, 0, 0),
        fs_before_snapshot={},
        run_store_backend=_RunStoreStub(),
        run_projection_service=_ProjectionStub(),
        audit_service=audit_service,
        build_run_bundle=lambda _run_dir, _debug: "bundle.zip",
        summarize_terminal_error_message=lambda value: str(value) if value else None,
        execution_mode="interactive",
        options={"execution_mode": "interactive"},
        adapter=None,
    )


def test_audit_finalizer_persists_meta_auth_detection_and_auth_session(tmp_path: Path) -> None:
    finalize_input = _build_finalize_input(tmp_path, audit_service=RunAuditService())

    RunAttemptAuditFinalizer().finalize(
        inputs=finalize_input,
        finished_at=datetime(2026, 4, 16, 10, 5, 0),
    )

    meta_path = finalize_input.context.run_dir / ".audit" / "meta.1.json"
    assert meta_path.exists()
    meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta_payload["status"] == "succeeded"
    assert meta_payload["auth_detection"]["classification"] == "auth_required"
    assert meta_payload["auth_session"]["session_id"] == "auth-1"


def test_audit_finalizer_warns_but_does_not_raise_on_write_failure(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    finalize_input = _build_finalize_input(tmp_path, audit_service=_FailingAuditService())

    with caplog.at_level(logging.WARNING):
        RunAttemptAuditFinalizer().finalize(
            inputs=finalize_input,
            finished_at=datetime(2026, 4, 16, 10, 5, 0),
        )

    assert "Failed to write attempt audit artifacts" in caplog.text
