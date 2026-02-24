import json
from pathlib import Path

import pytest

from server.services.run_observability import RunObservabilityService


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


def test_list_event_history_rewrites_seq_to_global_monotonic(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-global"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-02-24T00:00:00"}),
        encoding="utf-8",
    )
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

    monkeypatch.setattr(
        "server.services.run_observability.RunObservabilityService._materialize_protocol_stream",
        lambda self, **_kwargs: {"rasp_events": [], "fcmp_events": []},
    )

    service = RunObservabilityService()
    rows = service.list_event_history(run_dir=run_dir, request_id=None)
    assert [row["seq"] for row in rows] == [1, 2, 3, 4]
    assert [row["meta"]["local_seq"] for row in rows] == [1, 2, 1, 2]
    assert [row["meta"]["attempt"] for row in rows] == [1, 1, 2, 2]


@pytest.mark.asyncio
async def test_iter_sse_events_respects_global_cursor_across_attempts(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-global-cursor"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-02-24T00:00:00"}),
        encoding="utf-8",
    )
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

    monkeypatch.setattr(
        "server.services.run_observability.RunObservabilityService._materialize_protocol_stream",
        lambda self, **_kwargs: {"rasp_events": [], "fcmp_events": []},
    )

    service = RunObservabilityService()
    emitted = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id=None,
        cursor=2,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=0.2,
    ):
        emitted.append(item)
    chat_seqs = [item["data"]["seq"] for item in emitted if item["event"] == "chat_event"]
    assert chat_seqs == [3, 4]
