from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from server.models import EngineInteractiveProfile
from server.runtime.adapter.types import EngineRunResult
from server.runtime.protocol.event_protocol import build_fcmp_events, build_rasp_events
from server.services.orchestration.run_attempt_execution_service import RunAttemptExecutionResult
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptOutcomeInputs,
    RunAttemptOutcomeService,
)
from server.services.orchestration.run_attempt_preparation_service import RunAttemptContext
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest
from server.services.orchestration.run_output_convergence_service import OutputConvergenceResult


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

    def append_output_repair_record(self, **_kwargs: Any) -> None:
        return None

    def append_internal_schema_warning(self, **_kwargs: Any) -> None:
        return None

    def append_orchestrator_event(self, **_kwargs: Any) -> None:
        return None

    def find_done_markers(self, **_kwargs: Any) -> dict[str, Any]:
        marker = {
            "stream": "assistant",
            "byte_from": 0,
            "byte_to": 0,
            "payload": {"__SKILL_DONE__": True, "summary": "fallback"},
        } if self.done_marker_found else None
        return {
            "done_signal_found": False,
            "done_marker_found": self.done_marker_found,
            "done_marker_count": 1 if self.done_marker_found else 0,
            "first_marker": marker,
        }


class _FakeAuthService:
    def __init__(
        self,
        *,
        pending_auth: dict[str, Any] | None = None,
        custom_pending_auth: dict[str, Any] | None = None,
    ) -> None:
        self.pending_auth = pending_auth
        self.custom_pending_auth = custom_pending_auth

    async def create_pending_auth(self, **_kwargs: Any) -> _PendingModel | None:
        if self.pending_auth is None:
            return None
        return _PendingModel(self.pending_auth)

    async def create_custom_provider_pending_auth(self, **_kwargs: Any) -> _PendingModel:
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


async def _consume_handle(_handle_id: str) -> dict[str, Any]:
    return {"status": "stored"}


def execute_protocol_core_fixture(
    fixture: dict[str, Any],
    *,
    tmp_path: Path,
) -> tuple[list[Any], list[Any]]:
    inputs = fixture.get("inputs", {})
    run_dir = tmp_path / fixture["fixture_id"]
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = logs_dir / "stdout.txt"
    stderr_path = logs_dir / "stderr.txt"
    stdout_path.write_text(str(inputs.get("stdout", "")), encoding="utf-8")
    stderr_path.write_text(str(inputs.get("stderr", "")), encoding="utf-8")

    engine_obj = fixture.get("engine")
    if not isinstance(engine_obj, str) or engine_obj == "common":
        raise RuntimeError("Protocol-core fixture requires a concrete engine")
    status_hint = str(inputs.get("status_hint", "succeeded"))
    pending_context = inputs.get("pending_context")

    rasp_events = build_rasp_events(
        run_id=f"golden-{fixture['fixture_id']}",
        engine=engine_obj,
        attempt_number=1,
        status=status_hint,
        pending_interaction=pending_context if isinstance(pending_context, dict) else None,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    fcmp_events = build_fcmp_events(rasp_events, status=status_hint)
    return rasp_events, fcmp_events


def _build_outcome_context(tmp_path: Path, context_payload: dict[str, Any]) -> RunAttemptContext:
    run_dir = tmp_path / context_payload.get("run_dir_name", "run")
    run_dir.mkdir(parents=True, exist_ok=True)
    request_payload = context_payload.get("request", {})
    interactive_profile_payload = context_payload.get("interactive_profile")
    interactive_profile = None
    if isinstance(interactive_profile_payload, dict):
        interactive_profile = EngineInteractiveProfile(**interactive_profile_payload)

    return RunAttemptContext(
        request=RunJobRequest(
            run_id=str(request_payload.get("run_id", "run-1")),
            skill_id=str(request_payload.get("skill_id", "skill-1")),
            engine_name=str(request_payload.get("engine_name", "codex")),
            options=dict(request_payload.get("options", {})),
        ),
        run_dir=run_dir,
        request_record=dict(context_payload.get("request_record", {"request_id": "req-1"})),
        request_id=str(context_payload.get("request_id", "req-1")),
        execution_mode=str(context_payload.get("execution_mode", "auto")),
        conversation_mode=str(context_payload.get("conversation_mode", "non_session")),
        session_capable=bool(context_payload.get("session_capable", False)),
        is_interactive=bool(context_payload.get("is_interactive", False)),
        interactive_auto_reply=bool(context_payload.get("interactive_auto_reply", False)),
        can_wait_for_user=bool(context_payload.get("can_wait_for_user", False)),
        can_persist_waiting_user=bool(context_payload.get("can_persist_waiting_user", False)),
        interactive_profile=interactive_profile,
        attempt_number=int(context_payload.get("attempt_number", 1)),
        skill=SimpleNamespace(max_attempt=context_payload.get("max_attempt")),
        adapter=object(),
        input_data=dict(context_payload.get("input_data", {"input": {}, "parameter": {}})),
        run_options=dict(context_payload.get("run_options", {})),
        custom_provider_model=(
            str(context_payload["custom_provider_model"])
            if isinstance(context_payload.get("custom_provider_model"), str)
            else None
        ),
    )


def _build_execution_result(execution_payload: dict[str, Any]) -> RunAttemptExecutionResult:
    exit_code = int(execution_payload.get("exit_code", 0))
    failure_reason_obj = execution_payload.get("failure_reason")
    failure_reason = str(failure_reason_obj) if isinstance(failure_reason_obj, str) else None
    raw_stdout = str(execution_payload.get("raw_stdout", ""))
    raw_stderr = str(execution_payload.get("raw_stderr", ""))
    auth_signal_snapshot = execution_payload.get("auth_signal_snapshot")
    runtime_warnings = execution_payload.get("runtime_warnings", [])

    engine_result = EngineRunResult(
        exit_code=exit_code,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        failure_reason=failure_reason,
        runtime_warnings=list(runtime_warnings) if isinstance(runtime_warnings, list) else [],
        auth_signal_snapshot=auth_signal_snapshot if isinstance(auth_signal_snapshot, dict) else None,
    )
    return RunAttemptExecutionResult(
        engine_result=engine_result,
        process_exit_code=exit_code,
        process_failure_reason=failure_reason,
        process_raw_stdout=raw_stdout,
        process_raw_stderr=raw_stderr,
        runtime_execution_warnings=list(runtime_warnings) if isinstance(runtime_warnings, list) else [],
        adapter_stream_parser=object(),
        auth_signal_snapshot=auth_signal_snapshot if isinstance(auth_signal_snapshot, dict) else None,
        run_handle_consumer=_consume_handle,
        live_runtime_emitter_factory=lambda: object(),
    )


async def execute_outcome_core_fixture(
    fixture: dict[str, Any],
    *,
    tmp_path: Path,
) -> Any:
    inputs = fixture.get("inputs", {})
    context_payload = inputs.get("context")
    execution_payload = inputs.get("execution")
    convergence_payload = inputs.get("convergence")
    auth_payload = inputs.get("auth", {})
    if not isinstance(context_payload, dict) or not isinstance(execution_payload, dict) or not isinstance(convergence_payload, dict):
        raise RuntimeError("Outcome-core fixture requires `context`, `execution`, and `convergence` inputs")

    context = _build_outcome_context(tmp_path, context_payload)
    execution = _build_execution_result(execution_payload)
    convergence = OutputConvergenceResult(**dict(convergence_payload))
    auth_service = _FakeAuthService(
        pending_auth=dict(auth_payload.get("pending_auth")) if isinstance(auth_payload.get("pending_auth"), dict) else None,
        custom_pending_auth=(
            dict(auth_payload.get("custom_pending_auth"))
            if isinstance(auth_payload.get("custom_pending_auth"), dict)
            else None
        ),
    )
    schema_validator = _FakeSchemaValidator(
        output_errors=list(auth_payload.get("schema_output_errors", []))
        if isinstance(auth_payload.get("schema_output_errors"), list)
        else [],
        permissive=bool(auth_payload.get("schema_permissive", False)),
    )
    audit_service = _FakeAuditService(done_marker_found=bool(auth_payload.get("done_marker_found", False)))

    async def _persist_waiting_interaction(**_kwargs: Any) -> str | None:
        value = auth_payload.get("persist_waiting_status")
        return str(value) if isinstance(value, str) else None

    async def _update_status(**_kwargs: Any) -> None:
        return None

    interaction_service = RunInteractionLifecycleService()
    interaction_service.persist_waiting_interaction = _persist_waiting_interaction  # type: ignore[method-assign]

    outcome_inputs = RunAttemptOutcomeInputs(
        context=context,
        execution=execution,
        run_id=str(inputs.get("run_id", "run-1")),
        request_id=context.request_id,
        request_record=context.request_record,
        options=dict(context.request.options),
        skill_id=context.request.skill_id,
        run_store_backend=SimpleNamespace(),
        run_output_convergence_service=_FakeConvergenceService(convergence),
        auth_orchestration_service=auth_service,
        audit_service=audit_service,
        schema_validator_backend=schema_validator,
        append_orchestrator_event=lambda **_kwargs: None,
        update_status=_update_status,
        resolve_provider_id=lambda **_kwargs: str(auth_payload.get("canonical_provider_id", "openai")),
        provider_unresolved_detail=lambda **_kwargs: "provider unresolved",
        summarize_terminal_error_message=lambda message: str(message) if isinstance(message, str) else None,
        resolve_hard_timeout_seconds=lambda _options: int(auth_payload.get("hard_timeout_sec", 300)),
        live_runtime_emitter_factory=execution.live_runtime_emitter_factory,
        collect_run_artifacts=lambda _run_dir: list(auth_payload.get("existing_artifacts", []))
        if isinstance(auth_payload.get("existing_artifacts"), list)
        else [],
        resolve_output_artifact_paths=lambda *, skill, run_dir, output_data: SimpleNamespace(
            output_data=dict(output_data),
            artifacts=list(auth_payload.get("resolved_artifacts", []))
            if isinstance(auth_payload.get("resolved_artifacts"), list)
            else [],
            warnings=list(auth_payload.get("artifact_warnings", []))
            if isinstance(auth_payload.get("artifact_warnings"), list)
            else [],
            missing_required_fields=list(auth_payload.get("missing_required_fields", []))
            if isinstance(auth_payload.get("missing_required_fields"), list)
            else [],
        ),
        interaction_service=interaction_service,
    )
    return await RunAttemptOutcomeService().resolve(inputs=outcome_inputs)
