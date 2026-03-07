from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from server.models import AuthMethod, AuthSessionPhase, AuthSubmission, AuthSubmissionKind, RunStatus
from server.runtime.auth_detection.types import AuthDetectionResult
from server.services.engine_management.engine_interaction_gate import EngineInteractionBusyError
from server.services.orchestration.run_audit_service import RunAuditService
from server.services.orchestration.run_auth_orchestration_service import RunAuthOrchestrationService


def _build_detection(**overrides) -> AuthDetectionResult:
    payload = {
        "classification": "auth_required",
        "subcategory": "api_key_missing",
        "confidence": "high",
        "engine": "opencode",
        "provider_id": "deepseek",
        "matched_rule_ids": ["opencode_deepseek_api_key_missing"],
        "evidence_sources": ["structured_ndjson"],
        "evidence_excerpt": "API key is missing",
        "details": {},
    }
    payload.update(overrides)
    return AuthDetectionResult(**payload)


def _read_state_payload(run_dir: Path) -> dict[str, object]:
    return json.loads((run_dir / ".state" / "state.json").read_text(encoding="utf-8"))


def test_available_methods_for_uses_strategy_service(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_strategy_service.methods_for_conversation",
        lambda **_kwargs: ("callback", "device_auth"),
    )
    service = RunAuthOrchestrationService()

    methods = service._available_methods_for("codex", None)  # noqa: SLF001

    assert methods == [AuthMethod.CALLBACK, AuthMethod.DEVICE_AUTH]


def test_available_methods_for_drops_unknown_strategy_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_strategy_service.methods_for_conversation",
        lambda **_kwargs: ("callback", "unsupported_method"),
    )
    service = RunAuthOrchestrationService()

    methods = service._available_methods_for("codex", None)  # noqa: SLF001

    assert methods == [AuthMethod.CALLBACK]


def test_challenge_profile_appends_high_risk_notice_for_opencode_google() -> None:
    service = RunAuthOrchestrationService()

    _challenge_kind, _accepts_input, _input_kind, prompt = service._challenge_profile(  # noqa: SLF001
        engine="opencode",
        provider_id="google",
        auth_method=AuthMethod.CALLBACK,
    )

    assert "High risk!" in prompt


@pytest.mark.asyncio
async def test_create_pending_auth_multi_method_returns_selection(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-selection"
    run_dir.mkdir(parents=True, exist_ok=True)
    start_session = AsyncMock()
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.start_session",
        start_session,
    )

    backend = SimpleNamespace(
        clear_pending_auth=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
        set_pending_auth_method_selection=AsyncMock(),
        set_current_projection=AsyncMock(),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []

    service = RunAuthOrchestrationService()
    selection = await service.create_pending_auth(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        skill_id="demo-skill",
        engine_name="codex",
        options={"execution_mode": "interactive"},
        attempt_number=2,
        auth_detection=_build_detection(engine="codex", provider_id=None, subcategory="oauth_reauth"),
        run_store_backend=backend,
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda *_args, **_kwargs: None,
    )

    assert selection is not None
    assert selection.phase == AuthSessionPhase.METHOD_SELECTION
    assert selection.available_methods == [AuthMethod.CALLBACK, AuthMethod.DEVICE_AUTH]
    assert selection.ask_user is not None
    assert selection.ask_user.kind == "choose_one"
    assert selection.ask_user.hint == "Choose an authentication method."
    assert [item.value for item in selection.ask_user.options] == ["callback", "device_auth"]
    start_session.assert_not_awaited()
    backend.set_pending_auth_method_selection.assert_awaited_once()
    assert appended[0]["type_name"] == "auth.method.selection.required"
    state_payload = _read_state_payload(run_dir)
    assert state_payload["status"] == "waiting_auth"
    assert state_payload["pending"]["owner"] == "waiting_auth.method_selection"


@pytest.mark.asyncio
async def test_create_pending_auth_single_method_starts_session(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-create"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
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
    )

    backend = SimpleNamespace(
        clear_pending_auth_method_selection=AsyncMock(),
        set_pending_auth=AsyncMock(),
        set_current_projection=AsyncMock(),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []
    updated: list[RunStatus] = []

    service = RunAuthOrchestrationService()
    pending_auth = await service.create_pending_auth(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        skill_id="demo-skill",
        engine_name="opencode",
        options={"execution_mode": "interactive"},
        attempt_number=1,
        auth_detection=_build_detection(),
        canonical_provider_id="deepseek",
        run_store_backend=backend,
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda _run_dir, status, error=None: updated.append(status),
    )

    assert pending_auth is not None
    assert pending_auth.auth_session_id == "auth-1"
    assert pending_auth.auth_method == AuthMethod.API_KEY
    backend.set_pending_auth.assert_awaited_once()
    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.WAITING_AUTH)
    assert updated == []
    assert appended[0]["type_name"] == "auth.session.created"
    state_payload = _read_state_payload(run_dir)
    assert state_payload["status"] == "waiting_auth"
    assert state_payload["pending"]["owner"] == "waiting_auth.challenge_active"


@pytest.mark.asyncio
async def test_create_pending_auth_opencode_prefers_canonical_provider_over_detection_hint(
    monkeypatch,
    tmp_path: Path,
):
    run_dir = tmp_path / "run-auth-canonical-provider"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.start_session",
        lambda **_kwargs: {
            "session_id": "auth-1",
            "engine": "opencode",
            "provider_id": "google",
            "status": "waiting_user",
            "input_kind": "callback",
            "auth_url": "https://auth.example.test",
            "user_code": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
            "error": None,
        },
    )

    backend = SimpleNamespace(
        clear_pending_auth_method_selection=AsyncMock(),
        set_pending_auth=AsyncMock(),
        set_current_projection=AsyncMock(),
        update_run_status=AsyncMock(),
    )
    service = RunAuthOrchestrationService()
    pending_auth = await service.create_pending_auth(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        skill_id="demo-skill",
        engine_name="opencode",
        options={"execution_mode": "interactive"},
        attempt_number=1,
        auth_detection=_build_detection(provider_id="deepseek", subcategory="oauth_reauth"),
        canonical_provider_id="google",
        run_store_backend=backend,
        append_orchestrator_event=lambda **_kwargs: None,
        update_status=lambda *_args, **_kwargs: None,
    )

    assert pending_auth is not None
    assert pending_auth.provider_id == "google"


@pytest.mark.asyncio
async def test_create_pending_auth_single_method_busy_reprojects_active_challenge(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-busy"
    run_dir.mkdir(parents=True, exist_ok=True)

    def _raise(**_kwargs):  # noqa: ANN001
        raise EngineInteractionBusyError("busy")

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.start_session",
        _raise,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_active_session_snapshot",
        lambda: {
            "active": True,
            "session_id": "auth-1",
            "engine": "opencode",
            "provider_id": "deepseek",
            "auth_method": "api_key",
            "status": "waiting_user",
            "input_kind": "api_key",
            "auth_url": None,
            "user_code": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
            "error": None,
        },
    )

    backend = SimpleNamespace(
        clear_pending_auth_method_selection=AsyncMock(),
        set_pending_auth=AsyncMock(),
        set_current_projection=AsyncMock(),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []

    service = RunAuthOrchestrationService()
    selection = await service.create_pending_auth(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        skill_id="demo-skill",
        engine_name="opencode",
        options={"execution_mode": "interactive"},
        attempt_number=1,
        auth_detection=_build_detection(),
        canonical_provider_id="deepseek",
        run_store_backend=backend,
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda *_args, **_kwargs: None,
    )

    assert selection is not None
    assert selection.auth_session_id == "auth-1"
    assert selection.phase == AuthSessionPhase.CHALLENGE_ACTIVE
    backend.set_pending_auth.assert_awaited_once()
    assert appended[0]["type_name"] == "auth.challenge.updated"
    state_payload = _read_state_payload(run_dir)
    assert state_payload["pending"]["owner"] == "waiting_auth.challenge_active"


@pytest.mark.asyncio
async def test_select_auth_method_rejects_when_challenge_already_active(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-active"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    backend = SimpleNamespace(
        get_request=AsyncMock(return_value={"run_id": "run-1", "engine": "opencode"}),
        get_pending_auth=AsyncMock(
            return_value={
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "auth_method": "callback",
                "phase": "challenge_active",
                "source_attempt": 1,
            }
        ),
        get_pending_auth_method_selection=AsyncMock(return_value=None),
    )
    service = RunAuthOrchestrationService()

    with pytest.raises(HTTPException) as excinfo:
        await service.select_auth_method(
            request_id="req-1",
            run_id="run-1",
            selection=AuthMethod.CALLBACK,
            background_tasks=BackgroundTasks(),
            run_store_backend=backend,
            append_orchestrator_event=lambda **_kwargs: None,
            update_status=lambda *_args, **_kwargs: None,
            resume_run_job=AsyncMock(),
        )

    assert excinfo.value.status_code == 409
    assert "challenge already active" in str(excinfo.value.detail).lower()


@pytest.mark.asyncio
async def test_submit_auth_input_retry_does_not_persist_raw_secret(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-retry"
    run_dir.mkdir(parents=True, exist_ok=True)
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "opencode",
        "provider_id": "deepseek",
        "auth_method": "api_key",
        "challenge_kind": "api_key",
        "prompt": "API key required",
        "auth_url": None,
        "user_code": None,
        "instructions": "Paste API key",
        "accepts_chat_input": True,
        "input_kind": "api_key",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
    }

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.input_session",
        lambda *_args, **_kwargs: {
            "session_id": "auth-1",
            "engine": "opencode",
            "provider_id": "deepseek",
            "status": "waiting_user",
            "input_kind": "api_key",
            "auth_url": None,
            "user_code": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
            "error": "Invalid API key",
        },
    )

    backend = SimpleNamespace(
        get_pending_auth=AsyncMock(return_value=pending_auth),
        set_pending_auth=AsyncMock(),
        set_current_projection=AsyncMock(),
        get_auth_resume_context=AsyncMock(return_value={"source_attempt": 1, "runtime_input_kind": "api_key"}),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []

    service = RunAuthOrchestrationService()
    response = await service.submit_auth_input(
        request_id="req-1",
        run_id="run-1",
        request=AuthSubmission(kind=AuthSubmissionKind.API_KEY, value="SECRET-123"),
        auth_session_id="auth-1",
        background_tasks=BackgroundTasks(),
        run_store_backend=backend,
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda *_args, **_kwargs: None,
        resume_run_job=AsyncMock(),
    )

    assert response.status == RunStatus.WAITING_AUTH
    assert response.mode == "auth"
    assert appended[0]["type_name"] == "auth.input.accepted"
    assert appended[1]["type_name"] == "auth.challenge.updated"
    serialized = str(appended) + str(backend.set_pending_auth.await_args)
    assert "SECRET-123" not in serialized
    state_payload = _read_state_payload(run_dir)
    assert state_payload["pending"]["owner"] == "waiting_auth.challenge_active"


@pytest.mark.asyncio
async def test_submit_auth_input_completed_schedules_resume_attempt(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-completed"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result").mkdir(parents=True, exist_ok=True)
    (run_dir / "result" / "result.json").write_text(
        '{"status":"waiting_auth","pending_auth":{"auth_session_id":"auth-1"}}',
        encoding="utf-8",
    )
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "iflow",
        "provider_id": None,
        "auth_method": "authorization_code",
        "challenge_kind": "authorization_code",
        "prompt": "Paste authorization code",
        "auth_url": "https://auth.example.dev",
        "user_code": None,
        "instructions": "Paste the code from browser.",
        "accepts_chat_input": True,
        "input_kind": "authorization_code",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
    }

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.input_session",
        lambda *_args, **_kwargs: {
            "session_id": "auth-1",
            "engine": "iflow",
            "provider_id": None,
            "status": "completed",
            "input_kind": "text",
            "auth_url": None,
            "user_code": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
            "error": None,
        },
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.concurrency_manager.admit_or_reject",
        AsyncMock(side_effect=AssertionError("internal auth resume must not re-enter queue admission")),
    )

    backend = SimpleNamespace(
        get_pending_auth=AsyncMock(return_value=pending_auth),
        get_request=AsyncMock(
            return_value={
                "run_id": "run-1",
                "skill_id": "demo-skill",
                "engine": "iflow",
                "engine_options": {"model": "iflow-default"},
                "runtime_options": {"execution_mode": "interactive"},
            }
        ),
        clear_pending_auth=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
        set_current_projection=AsyncMock(),
        issue_resume_ticket=AsyncMock(return_value={"ticket_id": "ticket-1"}),
        mark_resume_ticket_dispatched=AsyncMock(return_value=True),
        update_run_status=AsyncMock(),
        get_auth_resume_context=AsyncMock(return_value={"source_attempt": 1, "runtime_input_kind": "text"}),
    )
    appended: list[dict[str, object]] = []
    background_tasks = BackgroundTasks()
    resume_run_job = AsyncMock()

    service = RunAuthOrchestrationService()
    response = await service.submit_auth_input(
        request_id="req-1",
        run_id="run-1",
        request=AuthSubmission(kind=AuthSubmissionKind.AUTHORIZATION_CODE, value="AUTH-CODE"),
        auth_session_id="auth-1",
        background_tasks=background_tasks,
        run_store_backend=backend,
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda *_args, **_kwargs: None,
        resume_run_job=resume_run_job,
    )

    assert response.status == RunStatus.QUEUED
    assert response.mode == "auth"
    assert appended[0]["type_name"] == "auth.input.accepted"
    assert appended[0]["data"]["accepted_at"]
    assert appended[1]["type_name"] == "auth.session.completed"
    assert appended[1]["data"]["resume_attempt"] == 2
    assert appended[1]["data"]["resume_ticket_id"] == "ticket-1"
    assert appended[1]["data"]["completed_at"]
    backend.clear_pending_auth.assert_awaited_once_with("req-1")
    backend.clear_pending_auth_method_selection.assert_awaited_once_with("req-1")
    backend.clear_auth_resume_context.assert_awaited_once_with("req-1")
    backend.issue_resume_ticket.assert_awaited_once()
    backend.mark_resume_ticket_dispatched.assert_awaited_once_with("req-1", "ticket-1")
    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.QUEUED)
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["options"]["__resume_ticket_id"] == "ticket-1"
    assert background_tasks.tasks[0].kwargs["options"]["__attempt_number_override"] == 2
    state_payload = _read_state_payload(run_dir)
    assert state_payload["status"] == "queued"
    assert state_payload["pending"]["owner"] is None


@pytest.mark.asyncio
async def test_submit_auth_input_writes_schema_valid_accepted_event(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-accepted-schema"
    run_dir.mkdir(parents=True, exist_ok=True)
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "opencode",
        "provider_id": "google",
        "auth_method": "callback",
        "challenge_kind": "callback_url",
        "prompt": "Paste callback URL",
        "auth_url": "https://auth.example.dev",
        "user_code": None,
        "instructions": "Paste callback URL here.",
        "accepts_chat_input": True,
        "input_kind": "callback_url",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
    }

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.input_session",
        lambda *_args, **_kwargs: {
            "session_id": "auth-1",
            "engine": "opencode",
            "provider_id": "google",
            "status": "waiting_user",
            "input_kind": "text",
            "auth_url": "https://auth.example.dev",
            "user_code": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
            "error": None,
        },
    )

    backend = SimpleNamespace(
        get_pending_auth=AsyncMock(return_value=pending_auth),
        set_pending_auth=AsyncMock(),
        set_current_projection=AsyncMock(),
        get_auth_resume_context=AsyncMock(return_value={"source_attempt": 1, "runtime_input_kind": "text"}),
        update_run_status=AsyncMock(),
    )
    service = RunAuthOrchestrationService()
    audit_service = RunAuditService()

    response = await service.submit_auth_input(
        request_id="req-1",
        run_id="run-1",
        request=AuthSubmission(
            kind=AuthSubmissionKind.CALLBACK_URL,
            value="http://localhost:3000/callback?code=done",
        ),
        auth_session_id="auth-1",
        background_tasks=BackgroundTasks(),
        run_store_backend=backend,
        append_orchestrator_event=audit_service.append_orchestrator_event,
        update_status=lambda *_args, **_kwargs: None,
        resume_run_job=AsyncMock(),
    )

    assert response.status == RunStatus.WAITING_AUTH
    event_lines = (run_dir / ".audit" / "orchestrator_events.1.jsonl").read_text(encoding="utf-8").splitlines()
    payloads = [json.loads(line) for line in event_lines if line.strip()]
    accepted = next(item for item in payloads if item["type"] == "auth.input.accepted")
    assert accepted["data"]["submission_kind"] == "callback_url"
    assert accepted["data"]["accepted_at"]


@pytest.mark.asyncio
async def test_get_auth_session_status_returns_backend_truth(monkeypatch):
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "status": "waiting_user",
            "error": None,
            "created_at": "2099-03-03T00:00:00Z",
            "expires_at": "2099-03-03T00:15:00Z",
        },
    )
    backend = SimpleNamespace(
        get_auth_session_status=AsyncMock(
            return_value={
                "waiting_auth": True,
                "phase": "challenge_active",
                "timed_out": False,
                "available_methods": ["callback", "authorization_code"],
                    "selected_method": "authorization_code",
                    "auth_session_id": "auth-1",
                    "challenge_kind": "authorization_code",
                    "timeout_sec": 900,
                    "created_at": "2099-03-03T00:00:00Z",
                    "expires_at": "2099-03-03T00:15:00Z",
                    "server_now": "2099-03-03T00:05:00Z",
                    "last_error": None,
                }
            )
        )

    service = RunAuthOrchestrationService()
    status = await service.get_auth_session_status(request_id="req-1", run_store_backend=backend)

    assert status.waiting_auth is True
    assert status.phase == AuthSessionPhase.CHALLENGE_ACTIVE
    assert status.selected_method == AuthMethod.AUTHORIZATION_CODE
    assert status.available_methods == [AuthMethod.CALLBACK, AuthMethod.AUTHORIZATION_CODE]


@pytest.mark.asyncio
async def test_get_auth_session_status_reconciles_completed_callback(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-status-reconcile"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "provider_id": None,
            "status": "succeeded",
            "created_at": "2026-03-03T00:00:00Z",
            "expires_at": "2026-03-03T00:15:00Z",
            "error": None,
        },
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.concurrency_manager.admit_or_reject",
        AsyncMock(side_effect=AssertionError("callback reconcile must not re-enter queue admission")),
    )
    backend = SimpleNamespace(
        get_auth_session_status=AsyncMock(
            side_effect=[
                {
                    "waiting_auth": True,
                    "phase": "challenge_active",
                    "timed_out": False,
                    "available_methods": ["callback"],
                    "selected_method": "callback",
                    "auth_session_id": "auth-1",
                    "challenge_kind": "callback_url",
                    "timeout_sec": 900,
                    "created_at": "2026-03-03T00:00:00Z",
                    "expires_at": "2026-03-03T00:15:00Z",
                    "server_now": "2026-03-03T00:05:00Z",
                    "last_error": None,
                },
                {
                    "waiting_auth": False,
                    "phase": None,
                    "timed_out": False,
                    "available_methods": [],
                    "selected_method": None,
                    "auth_session_id": None,
                    "challenge_kind": None,
                    "timeout_sec": None,
                    "created_at": None,
                    "expires_at": None,
                    "server_now": "2026-03-03T00:05:01Z",
                    "last_error": None,
                },
            ]
        ),
        get_request_id_for_auth_session=AsyncMock(return_value="req-1"),
        get_request=AsyncMock(
            return_value={
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo-skill",
                "engine": "codex",
                "engine_options": {"model": "gpt-5"},
                "runtime_options": {"execution_mode": "interactive"},
            }
        ),
        get_pending_auth=AsyncMock(return_value=None),
        get_auth_resume_context=AsyncMock(return_value=None),
        clear_pending_auth=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
        set_current_projection=AsyncMock(),
        issue_resume_ticket=AsyncMock(return_value={"ticket_id": "ticket-2"}),
        mark_resume_ticket_dispatched=AsyncMock(return_value=True),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []
    resume_run_job = AsyncMock()

    service = RunAuthOrchestrationService()
    status = await service.get_auth_session_status(
        request_id="req-1",
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda *_args, **_kwargs: None,
        resume_run_job=resume_run_job,
        run_store_backend=backend,
    )

    assert status.waiting_auth is False
    assert appended[0]["type_name"] == "auth.session.completed"
    assert appended[0]["data"]["resume_attempt"] == 2
    assert appended[0]["data"]["resume_ticket_id"] == "ticket-2"
    assert appended[0]["data"]["completed_at"]
    backend.clear_pending_auth.assert_awaited_once_with("req-1")
    backend.issue_resume_ticket.assert_awaited_once()
    backend.mark_resume_ticket_dispatched.assert_awaited_once_with("req-1", "ticket-2")
    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.QUEUED)
    state_payload = _read_state_payload(run_dir)
    assert state_payload["status"] == "queued"
    assert state_payload["pending"]["owner"] is None


@pytest.mark.asyncio
async def test_reconcile_waiting_auth_non_terminal_snapshot_is_noop(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-status-noop"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "opencode",
            "provider_id": "google",
            "status": "waiting_user",
            "created_at": "2030-03-03T00:00:00Z",
            "expires_at": "2030-03-03T00:15:00Z",
            "error": None,
        },
    )
    backend = SimpleNamespace(
        get_auth_session_status=AsyncMock(
            return_value={
                "waiting_auth": True,
                "phase": "challenge_active",
                "timed_out": False,
                "available_methods": ["callback"],
                "selected_method": "callback",
                "auth_session_id": "auth-1",
                "challenge_kind": "callback_url",
                "timeout_sec": 900,
                "created_at": "2030-03-03T00:00:00Z",
                "expires_at": "2030-03-03T00:15:00Z",
                "server_now": "2030-03-03T00:05:00Z",
                "last_error": None,
            }
        ),
        issue_resume_ticket=AsyncMock(),
        mark_resume_ticket_dispatched=AsyncMock(),
        clear_pending_auth=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
    )
    service = RunAuthOrchestrationService()

    changed = await service.reconcile_waiting_auth(
        request_id="req-1",
        append_orchestrator_event=lambda **_kwargs: None,
        update_status=lambda *_args, **_kwargs: None,
        resume_run_job=AsyncMock(),
        run_store_backend=backend,
    )

    assert changed is False
    backend.issue_resume_ticket.assert_not_awaited()
    backend.mark_resume_ticket_dispatched.assert_not_awaited()
    backend.clear_pending_auth.assert_not_awaited()
    backend.clear_pending_auth_method_selection.assert_not_awaited()
    backend.clear_auth_resume_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_auth_input_completed_session_returns_conflict_not_500(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-completed-conflict"
    run_dir.mkdir(parents=True, exist_ok=True)
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "codex",
        "provider_id": None,
        "auth_method": "callback",
        "challenge_kind": "callback_url",
        "prompt": "Paste callback URL",
        "auth_url": "https://auth.example.dev",
        "user_code": None,
        "instructions": "Paste callback URL here.",
        "accepts_chat_input": True,
        "input_kind": "callback_url",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
    }

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.input_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("Auth session already finished")),
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "provider_id": None,
            "status": "succeeded",
            "created_at": "2026-03-03T00:00:00Z",
            "expires_at": "2026-03-03T00:15:00Z",
            "error": None,
        },
    )
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )

    backend = SimpleNamespace(
        get_pending_auth=AsyncMock(return_value=pending_auth),
        get_auth_resume_context=AsyncMock(return_value={"source_attempt": 1, "runtime_input_kind": "text"}),
        get_request_id_for_auth_session=AsyncMock(return_value="req-1"),
        get_request=AsyncMock(
            return_value={
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo-skill",
                "engine": "codex",
                "engine_options": {"model": "gpt-5"},
                "runtime_options": {"execution_mode": "interactive"},
            }
        ),
        clear_pending_auth=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
        set_current_projection=AsyncMock(),
        issue_resume_ticket=AsyncMock(return_value={"ticket_id": "ticket-3"}),
        mark_resume_ticket_dispatched=AsyncMock(return_value=True),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []

    service = RunAuthOrchestrationService()
    with pytest.raises(HTTPException) as excinfo:
        await service.submit_auth_input(
            request_id="req-1",
            run_id="run-1",
            request=AuthSubmission(kind=AuthSubmissionKind.CALLBACK_URL, value="http://localhost/callback?code=done"),
            auth_session_id="auth-1",
            background_tasks=BackgroundTasks(),
            run_store_backend=backend,
            append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
            update_status=lambda *_args, **_kwargs: None,
            resume_run_job=AsyncMock(),
        )

    assert excinfo.value.status_code == 409
    assert "completed" in str(excinfo.value.detail).lower()
    assert any(item["type_name"] == "auth.input.accepted" for item in appended)
    assert any(item["type_name"] == "auth.session.completed" for item in appended)
    assert any(item["data"].get("completed_at") for item in appended if item["type_name"] == "auth.session.completed")
    backend.issue_resume_ticket.assert_awaited_once()
    backend.mark_resume_ticket_dispatched.assert_awaited_once_with("req-1", "ticket-3")


@pytest.mark.asyncio
async def test_get_auth_session_status_times_out_missing_session_marks_failed(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-timeout"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    def _missing_session(_session_id: str) -> dict[str, object]:
        raise KeyError("auth-1")

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.engine_auth_flow_manager.get_session",
        _missing_session,
    )

    backend = SimpleNamespace(
        get_auth_session_status=AsyncMock(
            side_effect=[
                {
                    "waiting_auth": True,
                    "phase": "challenge_active",
                    "timed_out": True,
                    "available_methods": ["callback"],
                    "selected_method": "callback",
                    "auth_session_id": "auth-1",
                    "challenge_kind": "callback_url",
                    "timeout_sec": 900,
                    "created_at": "2026-03-03T00:00:00Z",
                    "expires_at": "2026-03-03T00:15:00Z",
                    "server_now": "2026-03-03T00:16:00Z",
                    "last_error": None,
                },
                {
                    "waiting_auth": False,
                    "phase": None,
                    "timed_out": True,
                    "available_methods": [],
                    "selected_method": None,
                    "auth_session_id": None,
                    "challenge_kind": None,
                    "timeout_sec": None,
                    "created_at": None,
                    "expires_at": None,
                    "server_now": "2026-03-03T00:16:01Z",
                    "last_error": "timed out",
                },
            ]
        ),
        get_request=AsyncMock(
            return_value={
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo-skill",
                "engine": "codex",
                "engine_options": {"model": "gpt-5"},
                "runtime_options": {"execution_mode": "interactive"},
            }
        ),
        get_pending_auth=AsyncMock(
            return_value={
                "auth_session_id": "auth-1",
                "source_attempt": 3,
                "auth_method": "callback",
            }
        ),
        get_auth_resume_context=AsyncMock(return_value={"source_attempt": 3}),
        get_effective_session_timeout=AsyncMock(return_value=1200),
        clear_pending_auth=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
        set_current_projection=AsyncMock(),
        update_run_status=AsyncMock(),
    )
    appended: list[dict[str, object]] = []
    updated: list[tuple[RunStatus, object]] = []

    service = RunAuthOrchestrationService()
    status = await service.get_auth_session_status(
        request_id="req-1",
        append_orchestrator_event=lambda **kwargs: appended.append(kwargs),
        update_status=lambda _run_dir, status, error=None, effective_session_timeout_sec=None: updated.append(
            (status, effective_session_timeout_sec)
        ),
        resume_run_job=AsyncMock(),
        run_store_backend=backend,
    )

    assert status.waiting_auth is False
    assert appended[0]["type_name"] == "auth.session.timed_out"
    assert updated == [(RunStatus.FAILED, 1200)]
    backend.clear_pending_auth.assert_awaited_once_with("req-1")
    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.FAILED)


@pytest.mark.asyncio
async def test_engine_callback_dispatch_schedules_reconcile(monkeypatch):
    service = RunAuthOrchestrationService()
    handle_callback_completion = AsyncMock()
    monkeypatch.setattr(service, "handle_callback_completion", handle_callback_completion)
    monkeypatch.setattr(
        service,
        "_resolve_runtime_handlers",
        lambda **_kwargs: (
            lambda **_kwargs2: None,
            lambda *_args, **_kwargs2: None,
            AsyncMock(),
        ),
    )
    coroutines: list[object] = []

    class _DummyFuture:
        def add_done_callback(self, callback):  # noqa: ANN001
            callback(self)

        def result(self):
            return None

    def _run_threadsafe(coro, _loop):  # noqa: ANN001
        coroutines.append(coro)
        return _DummyFuture()

    class _DummyLoop:
        def is_closed(self) -> bool:
            return False

    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service.asyncio.run_coroutine_threadsafe",
        _run_threadsafe,
    )
    service._callback_dispatch_loop = _DummyLoop()

    service._dispatch_engine_callback_completion({"session_id": "auth-1", "status": "succeeded"})
    assert len(coroutines) == 1
    await coroutines[0]

    handle_callback_completion.assert_awaited_once()
