import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from server.runtime.observability.run_observability import RunObservabilityService
from tests.common.workspace_layout_helpers import layout_record, make_layout, state_payload


def _fcmp_event(*, attempt: int, seq: int, type_name: str, data: dict) -> dict:
    return {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-global-seq",
        "seq": seq,
        "ts": f"2026-02-24T00:00:0{attempt}{seq}",
        "engine": "codex",
        "type": type_name,
        "data": data,
        "meta": {"attempt": attempt},
    }


def _write_state_file(run_dir: Path, *, status: str) -> None:
    state_path = run_dir / ".state" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "request_id": run_dir.name,
                "run_id": run_dir.name,
                "status": status,
                "updated_at": "2026-02-24T00:00:00",
                "current_attempt": 2,
                "state_phase": {
                    "waiting_auth_phase": None,
                    "dispatch_phase": None,
                },
                "pending": {
                    "owner": "waiting_user" if status == "waiting_user" else None,
                    "interaction_id": 1 if status == "waiting_user" else None,
                    "auth_session_id": None,
                    "payload": None,
                },
                "resume": {
                    "resume_ticket_id": None,
                    "resume_cause": None,
                    "source_attempt": None,
                    "target_attempt": None,
                },
                "runtime": {},
                "error": None,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


def _bind_request_store(monkeypatch, service: RunObservabilityService, *, run_dir: Path, status: str = "waiting_user") -> str:
    request_id = "req-global-seq"
    run_id = "run-global-seq"
    record = layout_record(
        request_id=request_id,
        run_id=run_id,
        workspace=run_dir,
        namespace="demo.1",
        status=status,
    )
    state = state_payload(
        request_id=request_id,
        run_id=run_id,
        status=status,
        current_attempt=2,
        pending_interaction_id=1 if status == "waiting_user" else None,
        pending_owner="waiting_user" if status == "waiting_user" else None,
    )
    store = type("Store", (), {})()
    store.get_request_with_run = AsyncMock(return_value=record)
    store.get_request = AsyncMock(return_value=record)
    store.get_run_state = AsyncMock(return_value=state)
    store.get_current_projection = AsyncMock(return_value=state)
    store.get_pending_interaction = AsyncMock(return_value=None)
    store.get_pending_auth = AsyncMock(return_value=None)
    store.get_interaction_count = AsyncMock(return_value=1)
    monkeypatch.setattr(service, "_run_store", lambda: store)
    return request_id


@pytest.mark.asyncio
async def test_list_event_history_rewrites_seq_to_global_monotonic(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-global"
    audit_dir = make_layout(run_dir).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "fcmp_events.1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    _fcmp_event(
                        attempt=1,
                        seq=1,
                        type_name="conversation.state.changed",
                        data={
                            "from": "queued",
                            "to": "running",
                            "trigger": "turn.started",
                            "updated_at": "2026-02-24T00:00:01",
                            "pending_interaction_id": None,
                        },
                    )
                ),
                json.dumps(
                    _fcmp_event(
                        attempt=1,
                        seq=2,
                        type_name="assistant.message.final",
                        data={"message_id": "m1", "text": "hello"},
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "fcmp_events.2.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    _fcmp_event(
                        attempt=2,
                        seq=1,
                        type_name="interaction.reply.accepted",
                        data={
                            "interaction_id": 1,
                            "resolution_mode": "user_reply",
                            "accepted_at": "2026-02-24T00:00:03",
                            "response_preview": "world",
                        },
                    )
                ),
                json.dumps(
                    _fcmp_event(
                        attempt=2,
                        seq=2,
                        type_name="assistant.message.final",
                        data={"message_id": "m2", "text": "done"},
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for attempt in (1, 2):
        (audit_dir / f"events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"orchestrator_events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"stdout.{attempt}.log").write_text("", encoding="utf-8")

    async def _materialize(_self, **_kwargs):
        return {"rasp_events": [], "fcmp_events": []}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        _materialize,
    )

    service = RunObservabilityService()
    request_id = _bind_request_store(monkeypatch, service, run_dir=run_dir)
    rows = await service.list_event_history(run_dir=run_dir, request_id=request_id)
    assert [row["seq"] for row in rows] == [1, 2, 3, 4]
    assert [row["meta"]["local_seq"] for row in rows] == [1, 2, 1, 2]
    assert [row["meta"]["attempt"] for row in rows] == [1, 1, 2, 2]


@pytest.mark.asyncio
async def test_iter_sse_events_respects_global_cursor_across_attempts(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-global-cursor"
    audit_dir = make_layout(run_dir).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "fcmp_events.1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    _fcmp_event(
                        attempt=1,
                        seq=1,
                        type_name="assistant.message.final",
                        data={"message_id": "m1", "text": "q1"},
                    )
                ),
                json.dumps(
                    _fcmp_event(
                        attempt=1,
                        seq=2,
                        type_name="user.input.required",
                        data={"interaction_id": 1, "kind": "free_text", "prompt": "Provide next user turn"},
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "fcmp_events.2.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    _fcmp_event(
                        attempt=2,
                        seq=1,
                        type_name="interaction.reply.accepted",
                        data={
                            "interaction_id": 1,
                            "resolution_mode": "user_reply",
                            "accepted_at": "2026-02-24T00:00:05",
                            "response_preview": "my reply",
                        },
                    )
                ),
                json.dumps(
                    _fcmp_event(
                        attempt=2,
                        seq=2,
                        type_name="assistant.message.final",
                        data={"message_id": "m2", "text": "q2"},
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for attempt in (1, 2):
        (audit_dir / f"events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"orchestrator_events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"stdout.{attempt}.log").write_text("", encoding="utf-8")

    async def _materialize(_self, **_kwargs):
        return {"rasp_events": [], "fcmp_events": []}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        _materialize,
    )

    service = RunObservabilityService()
    request_id = _bind_request_store(monkeypatch, service, run_dir=run_dir)
    emitted = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id=request_id,
        cursor=2,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=0.2,
    ):
        emitted.append(item)
    chat_seqs = [item["data"]["seq"] for item in emitted if item["event"] == "chat_event"]
    assert chat_seqs == [3, 4]
