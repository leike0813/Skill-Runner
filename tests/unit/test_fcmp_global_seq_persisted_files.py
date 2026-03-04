import json
from pathlib import Path

import pytest

from server.runtime.observability.run_observability import RunObservabilityService


def _event(*, attempt: int, seq: int, type_name: str) -> dict:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-fcmp-seq",
        "seq": seq,
        "ts": f"2026-02-24T00:00:0{attempt}{seq}",
        "engine": "codex",
        "type": type_name,
        "data": {},
        "meta": {"attempt": attempt},
    }
    if type_name == "assistant.message.final":
        payload["data"] = {"message_id": f"m-{attempt}-{seq}", "text": f"text-{attempt}-{seq}"}
    elif type_name == "conversation.state.changed":
        payload["data"] = {
            "from": "queued",
            "to": "running",
            "trigger": "turn.started",
            "updated_at": "2026-02-24T00:00:00",
            "pending_interaction_id": None,
        }
    return payload


def _read_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _write_state_file(run_dir: Path, status: str) -> None:
    state_dir = run_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "request_id": "req-fcmp-seq",
                "run_id": run_dir.name,
                "status": status,
                "updated_at": "2026-02-24T00:00:00",
                "current_attempt": 2,
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
async def test_fcmp_seq_is_global_and_local_seq_is_persisted(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-global-seq-file"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_user")
    (audit_dir / "fcmp_events.1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_event(attempt=1, seq=1, type_name="conversation.state.changed")),
                json.dumps(_event(attempt=1, seq=2, type_name="assistant.message.final")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "fcmp_events.2.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_event(attempt=2, seq=1, type_name="conversation.state.changed")),
                json.dumps(_event(attempt=2, seq=2, type_name="assistant.message.final")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for attempt in (1, 2):
        (audit_dir / f"events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"orchestrator_events.{attempt}.jsonl").write_text("", encoding="utf-8")
        (audit_dir / f"stdout.{attempt}.log").write_text("", encoding="utf-8")
        (audit_dir / f"stderr.{attempt}.log").write_text("", encoding="utf-8")

    async def _materialize(_self, **_kwargs):
        return {"rasp_events": [], "fcmp_events": []}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        _materialize,
    )

    service = RunObservabilityService()
    await service.list_protocol_history(
        run_dir=run_dir,
        request_id=None,
        stream="fcmp",
        attempt=2,
    )

    rows_1 = _read_rows(audit_dir / "fcmp_events.1.jsonl")
    rows_2 = _read_rows(audit_dir / "fcmp_events.2.jsonl")
    assert [row["seq"] for row in rows_1] == [1, 2]
    assert [row["seq"] for row in rows_2] == [3, 4]
    assert [row["meta"]["local_seq"] for row in rows_1] == [1, 2]
    assert [row["meta"]["local_seq"] for row in rows_2] == [1, 2]
