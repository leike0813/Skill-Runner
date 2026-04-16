from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from server.models import EngineInteractiveProfile, RunStatus
from server.runtime.adapter.types import EngineRunResult
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionResult,
)
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptOutcomeInputs,
    RunAttemptOutcomeService,
)
from server.services.orchestration.run_attempt_preparation_service import RunAttemptContext
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest
from server.services.orchestration.run_output_convergence_service import OutputConvergenceResult
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)


class _PendingModel:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        _ = mode
        return dict(self.payload)


class _FakeConvergenceService:
    def __init__(self, result: OutputConvergenceResult) -> None:
        self.result = result

    async def converge(self, **_kwargs: Any) -> OutputConvergenceResult:
        return self.result


class _FakeAuditService:
    def __init__(self, *, done_marker_found: bool = False) -> None:
        self.done_marker_found = done_marker_found
        self.repair_records: list[dict[str, Any]] = []
        self.internal_schema_warnings: list[dict[str, Any]] = []
        self.orchestrator_events: list[dict[str, Any]] = []

    def append_output_repair_record(self, **kwargs: Any) -> None:
        self.repair_records.append(kwargs)

    def append_internal_schema_warning(self, **kwargs: Any) -> None:
        self.internal_schema_warnings.append(kwargs)

    def append_orchestrator_event(self, **kwargs: Any) -> None:
        self.orchestrator_events.append(kwargs)

    def contains_done_marker_in_stream(self, **_kwargs: Any) -> bool:
        return self.done_marker_found


class _FakeAuthService:
    def __init__(
        self,
        *,
        pending_auth: dict[str, Any] | None = None,
        custom_pending_auth: dict[str, Any] | None = None,
    ) -> None:
        self.pending_auth = pending_auth
        self.custom_pending_auth = custom_pending_auth
        self.create_pending_auth_calls: list[dict[str, Any]] = []
        self.create_custom_provider_pending_auth_calls: list[dict[str, Any]] = []

    async def create_pending_auth(self, **_kwargs: Any) -> _PendingModel | None:
        self.create_pending_auth_calls.append(dict(_kwargs))
        if self.pending_auth is None:
            return None
        return _PendingModel(self.pending_auth)

    async def create_custom_provider_pending_auth(self, **_kwargs: Any) -> _PendingModel:
        self.create_custom_provider_pending_auth_calls.append(dict(_kwargs))
        return _PendingModel(self.custom_pending_auth or {})


class _FakeSchemaValidator:
    def __init__(
        self,
        *,
        output_errors: list[str] | None = None,
        permissive: bool = False,
    ) -> None:
        self.output_errors = output_errors or []
        self.permissive = permissive

    def validate_output(self, _skill: Any, _output_data: dict[str, Any]) -> list[str]:
        return list(self.output_errors)

    def is_output_schema_too_permissive(self, _skill: Any) -> bool:
        return self.permissive


def _build_context(
    tmp_path: Path,
    *,
    is_interactive: bool = False,
    session_capable: bool = True,
    can_persist_waiting_user: bool = False,
    interactive_auto_reply: bool = False,
    interactive_profile: EngineInteractiveProfile | None = None,
    custom_provider_model: str | None = None,
    max_attempt: int | None = None,
) -> RunAttemptContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunAttemptContext(
        request=RunJobRequest(
            run_id="run-1",
            skill_id="skill-1",
            engine_name="codex",
            options={"execution_mode": "interactive" if is_interactive else "auto"},
        ),
        run_dir=run_dir,
        request_record={"request_id": "req-1"},
        request_id="req-1",
        execution_mode="interactive" if is_interactive else "auto",
        conversation_mode="session" if session_capable else "non_session",
        session_capable=session_capable,
        is_interactive=is_interactive,
        interactive_auto_reply=interactive_auto_reply,
        can_wait_for_user=is_interactive and session_capable,
        can_persist_waiting_user=can_persist_waiting_user,
        interactive_profile=interactive_profile,
        attempt_number=2,
        skill=SimpleNamespace(max_attempt=max_attempt),
        adapter=object(),
        input_data={"input": {"foo": "bar"}, "parameter": {"x": 1}},
        run_options={
            "__run_id": "run-1",
            "__attempt_number": 2,
            "__request_id": "req-1",
            "__engine_name": "codex",
        },
        custom_provider_model=custom_provider_model,
    )


def _build_execution(
    *,
    exit_code: int = 0,
    failure_reason: str | None = None,
    raw_stdout: str = "",
    raw_stderr: str = "",
    auth_signal_snapshot: dict[str, Any] | None = None,
) -> RunAttemptExecutionResult:
    engine_result = EngineRunResult(
        exit_code=exit_code,
        failure_reason=failure_reason,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
    )
    return RunAttemptExecutionResult(
        engine_result=engine_result,
        process_exit_code=exit_code,
        process_failure_reason=failure_reason,
        process_raw_stdout=raw_stdout,
        process_raw_stderr=raw_stderr,
        runtime_execution_warnings=[],
        adapter_stream_parser=object(),
        auth_signal_snapshot=auth_signal_snapshot,
        run_handle_consumer=_consume_handle,
        live_runtime_emitter_factory=lambda: object(),
    )


async def _consume_handle(_handle_id: str) -> dict[str, Any]:
    return {"status": "stored"}


def _build_inputs(
    *,
    context: RunAttemptContext,
    execution: RunAttemptExecutionResult,
    convergence: OutputConvergenceResult,
    auth_service: _FakeAuthService | None = None,
    schema_validator_backend: _FakeSchemaValidator | None = None,
    audit_service: _FakeAuditService | None = None,
    persist_waiting_status: str | None = None,
) -> tuple[RunAttemptOutcomeInputs, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    async def _persist_waiting_interaction(**_kwargs: Any) -> str | None:
        return persist_waiting_status

    async def _update_status(**_kwargs: Any) -> None:
        return None

    interaction_service = RunInteractionLifecycleService()

    inputs = RunAttemptOutcomeInputs(
        context=context,
        execution=execution,
        run_id="run-1",
        request_id=context.request_id,
        request_record=context.request_record,
        options=context.request.options,
        skill_id=context.request.skill_id,
        run_store_backend=SimpleNamespace(),
        run_output_convergence_service=_FakeConvergenceService(convergence),
        auth_orchestration_service=auth_service or _FakeAuthService(),
        audit_service=audit_service or _FakeAuditService(),
        schema_validator_backend=schema_validator_backend or _FakeSchemaValidator(),
        append_orchestrator_event=lambda **kwargs: events.append(kwargs),
        update_status=_update_status,
        resolve_provider_id=lambda **_kwargs: "openai",
        provider_unresolved_detail=lambda **_kwargs: "provider unresolved",
        summarize_terminal_error_message=lambda message: str(message) if isinstance(message, str) else None,
        resolve_hard_timeout_seconds=lambda _options: 300,
        live_runtime_emitter_factory=execution.live_runtime_emitter_factory,
        collect_run_artifacts=lambda _run_dir: ["artifacts/existing.txt"],
        resolve_output_artifact_paths=lambda *, skill, run_dir, output_data: SimpleNamespace(
            output_data=dict(output_data),
            artifacts=["artifacts/final.txt"],
            warnings=[],
            missing_required_fields=[],
        ),
        interaction_service=interaction_service,
    )
    interaction_service.persist_waiting_interaction = _persist_waiting_interaction  # type: ignore[method-assign]
    return inputs, events


@pytest.mark.asyncio
async def test_resolve_success_final_branch(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    execution = _build_execution()
    convergence = OutputConvergenceResult(
        output_data={"summary": "done"},
        has_structured_output=True,
        done_signal_found=True,
        repair_level="deterministic_generic",
    )
    inputs, events = _build_inputs(context=context, execution=execution, convergence=convergence)

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.SUCCEEDED
    assert outcome.output_data == {"summary": "done"}
    assert outcome.artifacts == ["artifacts/final.txt"]
    assert outcome.repair_level == "deterministic_generic"
    assert "OUTPUT_REPAIRED_GENERIC" in outcome.warnings
    assert any(event["category"] == "diagnostic" for event in events)


@pytest.mark.asyncio
async def test_resolve_waiting_user_with_pending_candidate(tmp_path: Path) -> None:
    profile = EngineInteractiveProfile(reason="probe_ok", session_timeout_sec=900)
    context = _build_context(
        tmp_path,
        is_interactive=True,
        session_capable=True,
        can_persist_waiting_user=True,
        interactive_profile=profile,
    )
    execution = _build_execution()
    pending = {
        "interaction_id": 7,
        "kind": "open_text",
        "prompt": "Please continue.",
        "ui_hints": {},
        "options": [],
        "required_fields": [],
        "default_decision_policy": "engine_judgement",
    }
    convergence = OutputConvergenceResult(
        output_data={},
        has_structured_output=True,
        pending_interaction_candidate=pending,
    )
    inputs, _events = _build_inputs(context=context, execution=execution, convergence=convergence)

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.WAITING_USER
    assert outcome.pending_interaction is not None
    assert outcome.pending_interaction["interaction_id"] == 7


@pytest.mark.asyncio
async def test_resolve_waiting_auth_with_high_confidence_signal(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    execution = _build_execution(
        exit_code=1,
        failure_reason="AUTH_REQUIRED",
        auth_signal_snapshot={
            "required": True,
            "confidence": "high",
            "matched_pattern_id": "codex_missing_bearer_401",
        },
    )
    convergence = OutputConvergenceResult()
    auth_service = _FakeAuthService(
        pending_auth={
            "auth_session_id": "auth-1",
            "engine": "codex",
            "provider_id": "openai",
            "challenge_kind": "api_key",
        }
    )
    inputs, _events = _build_inputs(
        context=context,
        execution=execution,
        convergence=convergence,
        auth_service=auth_service,
    )

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.WAITING_AUTH
    assert outcome.pending_auth is not None
    assert outcome.pending_auth["auth_session_id"] == "auth-1"
    assert outcome.pending_auth_method_selection is None
    assert auth_service.create_pending_auth_calls[0]["last_error"] is None


@pytest.mark.asyncio
async def test_resolve_failure_when_non_session_interactive_cannot_wait(tmp_path: Path) -> None:
    context = _build_context(
        tmp_path,
        is_interactive=True,
        session_capable=False,
        can_persist_waiting_user=False,
    )
    execution = _build_execution()
    convergence = OutputConvergenceResult(
        output_data={},
        has_structured_output=True,
        pending_interaction_candidate={
            "interaction_id": 8,
            "kind": "open_text",
            "prompt": "Please continue.",
            "ui_hints": {},
            "options": [],
            "required_fields": [],
            "default_decision_policy": "engine_judgement",
        },
    )
    inputs, _events = _build_inputs(context=context, execution=execution, convergence=convergence)

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.FAILED
    assert outcome.normalized_error is not None
    assert outcome.normalized_error["code"] == "NON_SESSION_INTERACTIVE_REPLY_UNSUPPORTED"


@pytest.mark.asyncio
async def test_resolve_soft_completion_adds_warning(tmp_path: Path) -> None:
    profile = EngineInteractiveProfile(reason="probe_ok", session_timeout_sec=900)
    context = _build_context(
        tmp_path,
        is_interactive=True,
        session_capable=True,
        can_persist_waiting_user=True,
        interactive_profile=profile,
    )
    execution = _build_execution()
    convergence = OutputConvergenceResult(
        output_data={"summary": "partial"},
        has_structured_output=True,
        done_signal_found=False,
        schema_output_errors=[],
    )
    inputs, _events = _build_inputs(context=context, execution=execution, convergence=convergence)

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.SUCCEEDED
    assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in outcome.warnings


@pytest.mark.asyncio
async def test_resolve_custom_provider_post_execute_fallback_waits_for_auth(tmp_path: Path) -> None:
    context = _build_context(
        tmp_path,
        custom_provider_model="openrouter/qwen-3",
    )
    execution = _build_execution(exit_code=1, failure_reason="TIMEOUT")
    convergence = OutputConvergenceResult()
    auth_service = _FakeAuthService(
        custom_pending_auth={
            "auth_session_id": "auth-custom",
            "engine": "claude",
            "provider_id": "openrouter",
            "challenge_kind": "provider_config",
        }
    )
    inputs, _events = _build_inputs(
        context=context,
        execution=execution,
        convergence=convergence,
        auth_service=auth_service,
    )

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.WAITING_AUTH
    assert outcome.pending_auth is not None
    assert outcome.pending_auth["auth_session_id"] == "auth-custom"
    assert auth_service.create_custom_provider_pending_auth_calls[0]["last_error"] == "Authentication is required to continue."


@pytest.mark.asyncio
async def test_resolve_failed_prefers_semantic_turn_failed_message_over_exit_code(tmp_path: Path) -> None:
    context = _build_context(tmp_path)

    class _SemanticFailureAdapter:
        def parse_runtime_stream(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "parser": "codex_ndjson",
                "confidence": 0.95,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": ["turn.failed"],
                "turn_failed": True,
                "turn_failure_data": {
                    "message": "You've hit your usage limit. Upgrade to Plus.",
                    "source_type": "turn.failed",
                    "pattern_kind": "engine_rate_limit_hint",
                    "fatal": True,
                },
                "turn_markers": [
                    {
                        "marker": "failed",
                        "data": {
                            "message": "You've hit your usage limit. Upgrade to Plus.",
                            "source_type": "turn.failed",
                            "pattern_kind": "engine_rate_limit_hint",
                            "fatal": True,
                        },
                    }
                ],
            }

    context.adapter = _SemanticFailureAdapter()
    execution = _build_execution(exit_code=1, raw_stdout='{"type":"turn.failed"}')
    convergence = OutputConvergenceResult()
    inputs, _events = _build_inputs(context=context, execution=execution, convergence=convergence)

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.FAILED
    assert outcome.normalized_error is not None
    assert outcome.normalized_error["message"] == "You've hit your usage limit. Upgrade to Plus."
    assert outcome.terminal_error_summary == "You've hit your usage limit. Upgrade to Plus."


@pytest.mark.asyncio
async def test_resolve_waiting_auth_preserves_semantic_turn_failed_message_in_pending_auth_reason(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)

    class _UsageLimitAdapter:
        def parse_runtime_stream(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "parser": "codex_ndjson",
                "confidence": 0.95,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": ["turn.failed", "error"],
                "turn_failed": True,
                "turn_failure_data": {
                    "message": "You've hit your usage limit. Upgrade to Plus.",
                    "source_type": "turn.failed",
                    "pattern_kind": "engine_rate_limit_hint",
                    "fatal": True,
                },
                "diagnostic_events": [
                    {
                        "code": "ENGINE_RATE_LIMIT_HINT",
                        "severity": "warning",
                        "pattern_kind": "engine_rate_limit_hint",
                        "source_type": "type:error",
                        "message": "You've hit your usage limit. Upgrade to Plus.",
                    }
                ],
            }

    context.adapter = _UsageLimitAdapter()
    execution = _build_execution(
        exit_code=1,
        raw_stdout='{"type":"turn.failed"}',
        auth_signal_snapshot={
            "required": True,
            "confidence": "high",
            "matched_pattern_id": "codex_usage_limit_plus_reauth_required",
        },
    )
    convergence = OutputConvergenceResult()
    auth_service = _FakeAuthService(
        pending_auth={
            "auth_session_id": "auth-usage-limit",
            "engine": "codex",
            "provider_id": "openai",
            "challenge_kind": "api_key",
        }
    )
    inputs, _events = _build_inputs(
        context=context,
        execution=execution,
        convergence=convergence,
        auth_service=auth_service,
    )

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.WAITING_AUTH
    assert outcome.normalized_error is None
    assert auth_service.create_pending_auth_calls[0]["last_error"] == "You've hit your usage limit. Upgrade to Plus."


@pytest.mark.asyncio
async def test_resolve_waiting_auth_failfast_falls_back_to_diagnostic_message_for_pending_auth_reason(
    tmp_path: Path,
) -> None:
    context = _build_context(tmp_path)

    class _FailFastAuthAdapter:
        def parse_runtime_stream(self, **_kwargs: Any) -> dict[str, Any]:
            return {
                "parser": "codex_ndjson",
                "confidence": 0.9,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": ["error"],
                "turn_failed": False,
                "diagnostic_events": [
                    {
                        "code": "ENGINE_AUTH_HINT",
                        "severity": "warning",
                        "pattern_kind": "engine_auth_hint",
                        "source_type": "type:error",
                        "message": "Missing bearer or basic authentication in header.",
                    }
                ],
            }

    context.adapter = _FailFastAuthAdapter()
    execution = _build_execution(
        exit_code=143,
        failure_reason="AUTH_REQUIRED",
        raw_stdout='{"type":"error"}',
        auth_signal_snapshot={
            "required": True,
            "confidence": "high",
            "matched_pattern_id": "codex_missing_bearer_401",
        },
    )
    convergence = OutputConvergenceResult()
    auth_service = _FakeAuthService(
        pending_auth={
            "auth_session_id": "auth-failfast",
            "engine": "codex",
            "provider_id": "openai",
            "challenge_kind": "api_key",
        }
    )
    inputs, _events = _build_inputs(
        context=context,
        execution=execution,
        convergence=convergence,
        auth_service=auth_service,
    )

    outcome = await RunAttemptOutcomeService().resolve(inputs=inputs)

    assert outcome.final_status == RunStatus.WAITING_AUTH
    assert outcome.normalized_error is None
    assert auth_service.create_pending_auth_calls[0]["last_error"] == "Missing bearer or basic authentication in header."
