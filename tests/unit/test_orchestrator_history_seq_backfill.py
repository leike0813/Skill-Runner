import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from server.runtime.observability.run_observability import RunObservabilityService
from tests.common.workspace_layout_helpers import layout_record, make_layout, state_payload


def _write_state_file(run_dir: Path, status: str) -> None:
    state_dir = run_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "request_id": "req-orchestrator",
                "run_id": run_dir.name,
                "status": status,
                "updated_at": "2026-02-24T00:00:00",
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
                    "requested_execution_mode": None,
                    "effective_execution_mode": None,
                    "effective_interactive_require_user_reply": None,
                    "effective_interactive_reply_timeout_sec": None,
                    "effective_session_timeout_sec": None,
                },
                "error": None,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_list_protocol_history_backfills_orchestrator_seq(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-orchestrator"
    audit_dir = make_layout(run_dir).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "fcmp_events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "orchestrator_events.1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-02-24T00:00:00",
                        "attempt_number": 1,
                        "category": "lifecycle",
                        "type": "lifecycle.run.started",
                        "data": {"status": "running"},
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-02-24T00:00:01",
                        "attempt_number": 1,
                        "category": "interaction",
                        "type": "interaction.user_input.required",
                        "data": {"interaction_id": 1, "kind": "open_text"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    async def _materialize(_self, **_kwargs):
        return {"rasp_events": [], "fcmp_events": []}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        _materialize,
    )
    service = RunObservabilityService()
    request_id = "req-orchestrator"
    run_id = "run-orchestrator"
    record = layout_record(
        request_id=request_id,
        run_id=run_id,
        workspace=run_dir,
        namespace="demo.1",
        status="succeeded",
    )
    state = state_payload(
        request_id=request_id,
        run_id=run_id,
        status="succeeded",
        current_attempt=1,
    )
    store = type("Store", (), {})()
    store.get_request_with_run = AsyncMock(return_value=record)
    store.get_request = AsyncMock(return_value=record)
    store.get_run_state = AsyncMock(return_value=state)
    store.get_current_projection = AsyncMock(return_value=state)
    store.get_interaction_count = AsyncMock(return_value=0)
    monkeypatch.setattr(service, "_run_store", lambda: store)
    payload = await service.list_protocol_history(
        run_dir=run_dir,
        request_id=request_id,
        stream="orchestrator",
        attempt=1,
    )
    assert payload["attempt"] == 1
    assert [row["seq"] for row in payload["events"]] == [1, 2]
