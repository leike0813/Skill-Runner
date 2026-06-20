import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.services.orchestration.run_audit_service import RunAuditService


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


_TEST_NAMESPACE = "demo.1"


def _layout_fields(run_dir: Path, *, namespace: str = _TEST_NAMESPACE) -> dict:
    return {
        "workspace_id": run_dir.name,
        "workspace_dir": str(run_dir),
        "workspace_namespace": namespace,
        "result_path": str(run_dir / "result" / namespace / "result.json"),
        "input_manifest_path": str(run_dir / ".audit" / namespace / "input_manifest.json"),
    }


def _audit_dir(run_dir: Path, *, namespace: str = _TEST_NAMESPACE) -> Path:
    path = run_dir / ".audit" / namespace
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_state(
    run_dir: Path,
    status: str,
    *,
    error: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    payload = {
        "request_id": f"req-{run_dir.name}",
        "run_id": run_dir.name,
        "status": status,
        "updated_at": "2026-02-16T00:00:00",
        "current_attempt": 1,
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
            "requested_execution_mode": "interactive",
            "effective_execution_mode": "interactive",
            "effective_interactive_require_user_reply": True,
            "effective_interactive_reply_timeout_sec": None,
            "effective_session_timeout_sec": None,
        },
        "warnings": warnings or [],
        "error": error,
    }
    return payload


def _patch_projection_store(monkeypatch, *, recovery_info: dict | None = None) -> None:
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_current_projection",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.set_current_projection",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_auth",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_auth_method_selection",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.issue_resume_ticket",
        lambda *_args, **_kwargs: {"ticket_id": "ticket-test-1"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.mark_resume_ticket_dispatched",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_recovery_info",
        lambda _run_id: recovery_info
        or {
            "recovery_state": "none",
            "recovered_at": None,
            "recovery_reason": None,
        },
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_auth",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_auth_method_selection",
        lambda _request_id: None,
    )


@pytest.mark.asyncio
async def test_interactive_reply_branches_success_conflict_and_not_waiting(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-branches"
    audit_dir = _audit_dir(run_dir)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    state_box = {"payload": _write_state(run_dir, "waiting_user")}

    request_record = {
        "request_id": "req-branches",
        "run_id": "run-branches",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
    pending_state = {
        "pending": {
            "interaction_id": 3,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }
    _patch_projection_store(monkeypatch)

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_run_state",
        lambda _request_id: state_box["payload"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_interaction",
        lambda _request_id: pending_state["pending"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interaction_reply",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.submit_interaction_reply",
        lambda **_kwargs: "accepted",
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.update_run_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interactive_profile",
        lambda _request_id: {},
    )
    monkeypatch.setattr(
        "server.routers.jobs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.run_job",
        AsyncMock(return_value=None),
    )

    accepted = await _request(
        "POST",
        "/v1/jobs/req-branches/interaction/reply",
        json={"interaction_id": 3, "response": {"answer": "ok"}},
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["status"] == "queued"

    state_box["payload"] = _write_state(run_dir, "waiting_user")
    stale = await _request(
        "POST",
        "/v1/jobs/req-branches/interaction/reply",
        json={"interaction_id": 99, "response": {"answer": "stale"}},
    )
    assert stale.status_code == 409

    state_box["payload"] = _write_state(run_dir, "running")
    not_waiting = await _request(
        "POST",
        "/v1/jobs/req-branches/interaction/reply",
        json={"interaction_id": 3, "response": {"answer": "late"}},
    )
    assert not_waiting.status_code == 409


@pytest.mark.asyncio
async def test_client_pending_reply_flow_reaches_terminal(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-e2e"
    audit_dir = _audit_dir(run_dir)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "input_manifest.json").write_text(
        json.dumps({"skill_id": "demo", "engine": "gemini"}),
        encoding="utf-8",
    )
    state_box = {"payload": _write_state(run_dir, "waiting_user")}

    request_record = {
        "request_id": "req-e2e",
        "run_id": "run-e2e",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
    pending_state = {
        "pending": {
            "interaction_id": 7,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }
    _patch_projection_store(monkeypatch)

    async def _run_job(**_kwargs):
        pending_state["pending"] = None
        state_box["payload"] = _write_state(
            run_dir,
            "succeeded",
            warnings=["INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"],
        )

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_run_state",
        lambda _request_id: state_box["payload"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_interaction",
        lambda _request_id: pending_state["pending"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interaction_count",
        lambda _request_id: 1,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_auto_decision_stats",
        lambda _request_id: {"auto_decision_count": 0, "last_auto_decision_at": None},
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interaction_reply",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.submit_interaction_reply",
        lambda **_kwargs: "accepted",
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.update_run_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interactive_profile",
        lambda _request_id: {},
    )
    monkeypatch.setattr(
        "server.routers.jobs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.run_job",
        AsyncMock(side_effect=_run_job),
    )

    status_before = await _request("GET", "/v1/jobs/req-e2e")
    assert status_before.status_code == 200
    body_before = status_before.json()
    assert body_before["status"] == "waiting_user"
    assert body_before["interaction_count"] == 1

    pending = await _request("GET", "/v1/jobs/req-e2e/interaction/pending")
    assert pending.status_code == 200
    assert pending.json()["pending"]["interaction_id"] == 7

    reply = await _request(
        "POST",
        "/v1/jobs/req-e2e/interaction/reply",
        json={"interaction_id": 7, "response": "继续执行"},
    )
    assert reply.status_code == 200
    assert reply.json()["accepted"] is True
    status_after = await _request("GET", "/v1/jobs/req-e2e")
    assert status_after.status_code == 200
    assert status_after.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_client_reply_flow_can_end_with_max_attempt_failed_reason(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-e2e-max-attempt"
    audit_dir = _audit_dir(run_dir)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "input_manifest.json").write_text(
        json.dumps({"skill_id": "demo", "engine": "gemini"}),
        encoding="utf-8",
    )
    state_box = {"payload": _write_state(run_dir, "waiting_user")}

    request_record = {
        "request_id": "req-e2e-max-attempt",
        "run_id": "run-e2e-max-attempt",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
    pending_state = {
        "pending": {
            "interaction_id": 9,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }
    _patch_projection_store(monkeypatch)

    async def _run_job(**_kwargs):
        pending_state["pending"] = None
        state_box["payload"] = _write_state(
            run_dir,
            "failed",
            error={
                "code": "INTERACTIVE_MAX_ATTEMPT_EXCEEDED",
                "message": "INTERACTIVE_MAX_ATTEMPT_EXCEEDED",
            },
        )

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_run_state",
        lambda _request_id: state_box["payload"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_interaction",
        lambda _request_id: pending_state["pending"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interaction_count",
        lambda _request_id: 2,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_auto_decision_stats",
        lambda _request_id: {"auto_decision_count": 0, "last_auto_decision_at": None},
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interaction_reply",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.submit_interaction_reply",
        lambda **_kwargs: "accepted",
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.update_run_status",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_interactive_profile",
        lambda _request_id: {},
    )
    monkeypatch.setattr(
        "server.routers.jobs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.run_job",
        AsyncMock(side_effect=_run_job),
    )

    status_before = await _request("GET", "/v1/jobs/req-e2e-max-attempt")
    assert status_before.status_code == 200
    assert status_before.json()["status"] == "waiting_user"

    reply = await _request(
        "POST",
        "/v1/jobs/req-e2e-max-attempt/interaction/reply",
        json={"interaction_id": 9, "response": "继续执行"},
    )
    assert reply.status_code == 200
    assert reply.json()["accepted"] is True

    status_after = await _request("GET", "/v1/jobs/req-e2e-max-attempt")
    assert status_after.status_code == 200
    body_after = status_after.json()
    assert body_after["status"] == "failed"


@pytest.mark.asyncio
async def test_auth_reply_callback_submit_records_accepted_event(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-route"
    audit_dir = _audit_dir(run_dir)
    state_box = {"payload": _write_state(run_dir, "waiting_auth")}

    request_record = {
        "request_id": "req-auth-route",
        "run_id": "run-auth-route",
        "skill_id": "demo",
        "engine": "opencode",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
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
    _patch_projection_store(monkeypatch)

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_run_state",
        lambda _request_id: state_box["payload"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_pending_auth",
        lambda _request_id: pending_auth,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_auth_resume_context",
        lambda _request_id: {"source_attempt": 1, "runtime_input_kind": "text"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.set_pending_auth",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.update_run_status",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.audit_service.append_orchestrator_event",
        RunAuditService().append_orchestrator_event,
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

    reply = await _request(
        "POST",
        "/v1/jobs/req-auth-route/interaction/reply",
        json={
            "mode": "auth",
            "auth_session_id": "auth-1",
            "submission": {
                "kind": "callback_url",
                "value": "http://localhost:3000/callback?code=done",
            },
        },
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["accepted"] is True
    assert body["status"] == "waiting_auth"
    event_lines = (audit_dir / "orchestrator_events.1.jsonl").read_text(encoding="utf-8").splitlines()
    payloads = [json.loads(line) for line in event_lines if line.strip()]
    assert any(item["type"] == "auth.input.accepted" for item in payloads)


@pytest.mark.asyncio
async def test_cancel_observability_matches_canceled_event_semantics(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-cancel"
    audit_dir = _audit_dir(run_dir)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    state_box = {"payload": _write_state(run_dir, "running")}

    request_record = {
        "request_id": "req-cancel",
        "run_id": "run-cancel",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
    _patch_projection_store(monkeypatch)

    async def _cancel_run(**_kwargs):
        state_box["payload"] = _write_state(
            run_dir,
            "canceled",
            error={"code": "CANCELED_BY_USER", "message": "Canceled by user request"},
        )
        return True

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_run_state",
        lambda _request_id: state_box["payload"],
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.cancel_run",
        AsyncMock(side_effect=_cancel_run),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )
    async def _iter_sse_events(**_kwargs):
        yield {"event": "snapshot", "data": {"status": "canceled", "cursor": 0}}
        yield {
            "event": "chat_event",
            "data": {
                "seq": 2,
                "type": "conversation.state.changed",
                "data": {
                    "from": "running",
                    "to": "canceled",
                    "trigger": "run.canceled",
                    "terminal": {"status": "canceled", "error": {"code": "CANCELED"}},
                },
            },
        }
    monkeypatch.setattr(
        "server.runtime.observability.run_read_facade.run_observability_service.iter_sse_events",
        _iter_sse_events,
    )

    cancel = await _request("POST", "/v1/jobs/req-cancel/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"
    assert cancel.json()["accepted"] is True

    events = await _request("GET", "/v1/jobs/req-cancel/events")
    assert events.status_code == 200
    assert "\"conversation.state.changed\"" in events.text
    assert "\"to\": \"canceled\"" in events.text
    assert "\"code\": \"CANCELED\"" in events.text


@pytest.mark.asyncio
async def test_recovered_waiting_user_still_supports_reply_and_cancel(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-recovered"
    audit_dir = _audit_dir(run_dir)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "input_manifest.json").write_text(
        json.dumps({"skill_id": "demo", "engine": "gemini"}),
        encoding="utf-8",
    )
    state_box = {"payload": _write_state(run_dir, "waiting_user")}

    request_record = {
        "request_id": "req-recovered",
        "run_id": "run-recovered",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
        **_layout_fields(run_dir),
    }
    pending_state = {"interaction_id": 42, "kind": "open_text", "prompt": "continue?"}
    _patch_projection_store(
        monkeypatch,
        recovery_info={
            "recovery_state": "recovered_waiting",
            "recovered_at": "2026-02-16T00:05:00",
            "recovery_reason": "resumable_waiting_preserved",
        },
    )

    monkeypatch.setattr("server.routers.jobs.run_store.get_request", lambda _request_id: request_record)
    monkeypatch.setattr("server.routers.jobs.run_store.get_run_state", lambda _request_id: state_box["payload"])
    monkeypatch.setattr("server.routers.jobs.run_store.get_pending_interaction", lambda _request_id: pending_state)
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_recovery_info",
        lambda _run_id: {
            "recovery_state": "recovered_waiting",
            "recovered_at": "2026-02-16T00:05:00",
            "recovery_reason": "resumable_waiting_preserved",
        },
    )
    monkeypatch.setattr("server.routers.jobs.run_store.get_interaction_count", lambda _request_id: 1)
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_auto_decision_stats",
        lambda _request_id: {"auto_decision_count": 0, "last_auto_decision_at": None},
    )
    monkeypatch.setattr("server.routers.jobs.run_store.get_interaction_reply", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("server.routers.jobs.run_store.submit_interaction_reply", lambda **_kwargs: "accepted")
    monkeypatch.setattr("server.routers.jobs.run_store.update_run_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("server.routers.jobs.run_store.get_interactive_profile", lambda _request_id: {})
    monkeypatch.setattr("server.routers.jobs.concurrency_manager.admit_or_reject", AsyncMock(return_value=True))
    monkeypatch.setattr("server.routers.jobs.job_orchestrator.run_job", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.jobs.job_orchestrator.cancel_run", AsyncMock(return_value=True))

    status = await _request("GET", "/v1/jobs/req-recovered")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "waiting_user"
    assert body["recovery_state"] == "recovered_waiting"
    assert body["recovery_reason"] == "resumable_waiting_preserved"

    reply = await _request(
        "POST",
        "/v1/jobs/req-recovered/interaction/reply",
        json={"interaction_id": 42, "response": "继续"},
    )
    assert reply.status_code == 200
    assert reply.json()["accepted"] is True

    cancel = await _request("POST", "/v1/jobs/req-recovered/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["accepted"] is True
