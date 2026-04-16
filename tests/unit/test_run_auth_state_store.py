import pytest

from server.services.orchestration.run_store_auth_state_store import RunAuthStateStore
from server.services.orchestration.run_store_database import RunStoreDatabase


@pytest.mark.asyncio
async def test_run_auth_state_store_resume_ticket_roundtrip_is_idempotent(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunAuthStateStore(database)

    first = await store.issue_resume_ticket(
        "req-1",
        cause="auth_completed",
        source_attempt=1,
        target_attempt=2,
        payload={"auth_session_id": "auth-1"},
    )
    second = await store.issue_resume_ticket(
        "req-1",
        cause="auth_completed",
        source_attempt=1,
        target_attempt=2,
        payload={"auth_session_id": "auth-1"},
    )

    assert second["ticket_id"] == first["ticket_id"]
    assert await store.mark_resume_ticket_dispatched("req-1", first["ticket_id"]) is True
    assert await store.mark_resume_ticket_started("req-1", first["ticket_id"], target_attempt=2) is True


@pytest.mark.asyncio
async def test_run_auth_state_store_pending_auth_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunAuthStateStore(database)

    await store.set_pending_auth(
        "req-1",
        {
            "auth_session_id": "auth-1",
            "engine": "codex",
            "provider_id": "openai",
            "auth_method": "auth_code_or_url",
            "challenge_kind": "auth_code_or_url",
            "prompt": "Authenticate",
            "accepts_chat_input": True,
            "created_at": "2026-04-16T00:00:00Z",
            "expires_at": "2026-04-16T01:00:00Z",
            "source_attempt": 1,
            "phase": "challenge_active",
        },
        auth_resume_context={"resume_ticket": "x"},
    )

    pending = await store.get_pending_auth("req-1")
    resume_context = await store.get_auth_resume_context("req-1")
    assert pending is not None
    assert pending["auth_session_id"] == "auth-1"
    assert resume_context == {"resume_ticket": "x"}


@pytest.mark.asyncio
async def test_run_auth_state_store_method_selection_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunAuthStateStore(database)

    await store.set_pending_auth_method_selection(
        "req-1",
        {
            "engine": "codex",
            "provider_id": "openai",
            "available_methods": ["auth_code_or_url"],
            "prompt": "Pick auth method",
            "source_attempt": 1,
            "phase": "method_selection",
            "ui_hints": {},
        },
    )

    pending = await store.get_pending_auth_method_selection("req-1")
    status = await store.get_auth_session_status("req-1")
    assert pending is not None
    assert pending["available_methods"] == ["auth_code_or_url"]
    assert status["phase"] == "method_selection"


@pytest.mark.asyncio
async def test_run_auth_state_store_durable_auth_session_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunAuthStateStore(database)

    await store.upsert_durable_auth_session(
        auth_session_id="auth-1",
        engine="qwen",
        provider_id="coding-plan-china",
        request_id="req-1",
        run_id="run-1",
        source_attempt=2,
        status="challenge_active",
        payload={
            "session_id": "auth-1",
            "engine": "qwen",
            "provider_id": "coding-plan-china",
            "status": "waiting_user",
            "transport": "oauth_proxy",
            "input_kind": "api_key",
            "created_at": "2026-04-16T00:00:00Z",
            "expires_at": "2026-04-16T00:15:00Z",
        },
        auth_method="api_key",
        challenge_kind="api_key",
        transport="oauth_proxy",
        input_kind="api_key",
        expires_at="2026-04-16T00:15:00Z",
    )

    session = await store.get_durable_auth_session("auth-1")
    assert session is not None
    assert session["scope_key"] == "qwen::coding-plan-china"
    assert session["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_get_auth_session_status_prefers_durable_auth_session_truth(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunAuthStateStore(database)

    await store.set_pending_auth(
        "req-1",
        {
            "auth_session_id": "auth-1",
            "engine": "qwen",
            "provider_id": "coding-plan-china",
            "auth_method": "api_key",
            "challenge_kind": "api_key",
            "prompt": "Authenticate",
            "accepts_chat_input": True,
            "created_at": "2026-04-16T00:00:00Z",
            "expires_at": "2026-04-16T00:10:00Z",
            "source_attempt": 1,
            "phase": "challenge_active",
            "last_error": None,
        },
    )
    await store.upsert_durable_auth_session(
        auth_session_id="auth-1",
        engine="qwen",
        provider_id="coding-plan-china",
        request_id="req-1",
        run_id="run-1",
        source_attempt=1,
        status="expired",
        payload={
            "session_id": "auth-1",
            "engine": "qwen",
            "provider_id": "coding-plan-china",
            "status": "expired",
            "transport": "oauth_proxy",
            "error": "Auth session expired",
            "created_at": "2026-04-16T00:00:00Z",
            "expires_at": "2026-04-16T00:10:00Z",
        },
        auth_method="api_key",
        challenge_kind="api_key",
        transport="oauth_proxy",
        expires_at="2026-04-16T00:10:00Z",
        last_error="Auth session expired",
    )

    status = await store.get_auth_session_status("req-1")

    assert status["timed_out"] is True
    assert status["last_error"] == "Auth session expired"
    assert status["transport"] == "oauth_proxy"
    assert status["session_status"] == "expired"
