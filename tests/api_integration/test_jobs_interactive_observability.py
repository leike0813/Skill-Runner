import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _write_status(run_dir: Path, status: str, *, error: dict | None = None) -> None:
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": status,
                "updated_at": "2026-02-16T00:00:00",
                "warnings": [],
                "error": error,
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_interactive_reply_branches_success_conflict_and_not_waiting(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-branches"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("", encoding="utf-8")
    _write_status(run_dir, "waiting_user")

    request_record = {
        "request_id": "req-branches",
        "run_id": "run-branches",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
    }
    pending_state = {
        "pending": {
            "interaction_id": 3,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
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

    _write_status(run_dir, "waiting_user")
    stale = await _request(
        "POST",
        "/v1/jobs/req-branches/interaction/reply",
        json={"interaction_id": 99, "response": {"answer": "stale"}},
    )
    assert stale.status_code == 409

    _write_status(run_dir, "running")
    not_waiting = await _request(
        "POST",
        "/v1/jobs/req-branches/interaction/reply",
        json={"interaction_id": 3, "response": {"answer": "late"}},
    )
    assert not_waiting.status_code == 409


@pytest.mark.asyncio
async def test_client_pending_reply_flow_reaches_terminal(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-e2e"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "input.json").write_text(json.dumps({"skill_id": "demo", "engine": "gemini"}), encoding="utf-8")
    _write_status(run_dir, "waiting_user")

    request_record = {
        "request_id": "req-e2e",
        "run_id": "run-e2e",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
    }
    pending_state = {
        "pending": {
            "interaction_id": 7,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }

    async def _run_job(**_kwargs):
        pending_state["pending"] = None
        _write_status(
            run_dir,
            "succeeded",
        )
        payload = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        payload["warnings"] = ["INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"]
        (run_dir / "status.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda _request_id: request_record,
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
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
    assert body_before["pending_interaction_id"] == 7
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
    assert status_after.json()["pending_interaction_id"] is None
    assert "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER" in status_after.json()["warnings"]


@pytest.mark.asyncio
async def test_client_reply_flow_can_end_with_max_attempt_failed_reason(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-e2e-max-attempt"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "input.json").write_text(json.dumps({"skill_id": "demo", "engine": "gemini"}), encoding="utf-8")
    _write_status(run_dir, "waiting_user")

    request_record = {
        "request_id": "req-e2e-max-attempt",
        "run_id": "run-e2e-max-attempt",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
    }
    pending_state = {
        "pending": {
            "interaction_id": 9,
            "kind": "open_text",
            "prompt": "continue?",
        }
    }

    async def _run_job(**_kwargs):
        pending_state["pending"] = None
        _write_status(
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
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
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
    assert status_before.json()["pending_interaction_id"] == 9

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
    assert body_after["pending_interaction_id"] is None
    assert body_after["error"]["code"] == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"


@pytest.mark.asyncio
async def test_cancel_observability_matches_canceled_event_semantics(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-cancel"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    _write_status(run_dir, "running")

    request_record = {
        "request_id": "req-cancel",
        "run_id": "run-cancel",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
    }

    async def _cancel_run(**_kwargs):
        _write_status(
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
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.routers.jobs.job_orchestrator.cancel_run",
        AsyncMock(side_effect=_cancel_run),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )

    cancel = await _request("POST", "/v1/jobs/req-cancel/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"
    assert cancel.json()["accepted"] is True

    events = await _request("GET", "/v1/jobs/req-cancel/events")
    assert events.status_code == 200
    assert "\"conversation.state.changed\"" in events.text
    assert "\"to\": \"canceled\"" in events.text
    assert "\"conversation.failed\"" in events.text
    assert "\"code\": \"CANCELED\"" in events.text


@pytest.mark.asyncio
async def test_recovered_waiting_user_still_supports_reply_and_cancel(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-recovered"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "input.json").write_text(json.dumps({"skill_id": "demo", "engine": "gemini"}), encoding="utf-8")
    _write_status(run_dir, "waiting_user")

    request_record = {
        "request_id": "req-recovered",
        "run_id": "run-recovered",
        "skill_id": "demo",
        "engine": "gemini",
        "engine_options": {},
        "runtime_options": {"execution_mode": "interactive"},
    }
    pending_state = {"interaction_id": 42, "kind": "open_text", "prompt": "continue?"}

    monkeypatch.setattr("server.routers.jobs.run_store.get_request", lambda _request_id: request_record)
    monkeypatch.setattr("server.routers.jobs.workspace_manager.get_run_dir", lambda _run_id: run_dir)
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
    assert body["pending_interaction_id"] == 42

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
