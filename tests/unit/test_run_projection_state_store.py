import pytest

from server.models import RunStatus
from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.orchestration.run_store_state_store import RunProjectionStateStore


@pytest.mark.asyncio
async def test_run_projection_state_store_roundtrip_current_projection(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    state_store = RunProjectionStateStore(database)

    await state_store.set_current_projection(
        "req-1",
        {
            "request_id": "req-1",
            "run_id": "run-1",
            "status": RunStatus.WAITING_USER.value,
            "updated_at": "2026-04-16T00:00:00",
            "current_attempt": 1,
            "pending_owner": "waiting_user",
            "pending_interaction_id": 7,
            "warnings": [],
        },
    )

    projection = await state_store.get_current_projection("req-1")
    assert projection is not None
    assert projection["status"] == RunStatus.WAITING_USER.value
    assert projection["pending_interaction_id"] == 7


@pytest.mark.asyncio
async def test_run_projection_state_store_derives_projection_from_run_state(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    state_store = RunProjectionStateStore(database)

    await state_store.set_run_state(
        "req-1",
        {
            "request_id": "req-1",
            "run_id": "run-1",
            "status": RunStatus.WAITING_AUTH.value,
            "current_attempt": 2,
            "pending": {
                "owner": "waiting_auth.challenge_active",
                "auth_session_id": "auth-1",
            },
            "resume": {},
            "runtime": {},
            "warnings": [],
            "updated_at": "2026-04-16T00:00:00",
        },
    )

    projection = await state_store.get_current_projection("req-1")
    assert projection is not None
    assert projection["status"] == RunStatus.WAITING_AUTH.value
    assert projection["pending_auth_session_id"] == "auth-1"


@pytest.mark.asyncio
async def test_run_projection_state_store_dispatch_state_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    state_store = RunProjectionStateStore(database)

    await state_store.set_dispatch_state(
        "req-1",
        {
                "request_id": "req-1",
                "run_id": "run-1",
                "dispatch_ticket_id": "ticket-1",
                "phase": "created",
                "worker_claim_id": None,
                "updated_at": "2026-04-16T00:00:00",
            },
    )

    dispatch = await state_store.get_dispatch_state("req-1")
    assert dispatch is not None
    assert dispatch["dispatch_ticket_id"] == "ticket-1"
