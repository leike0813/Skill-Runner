import json
from pathlib import Path

from server.services.run_observability import RunObservabilityService


def _fcmp_state_event(*, seq: int, attempt: int, to_state: str) -> dict:
    return {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": seq,
        "ts": "2026-02-24T00:00:00",
        "engine": "codex",
        "type": "conversation.state.changed",
        "data": {
            "from": "queued",
            "to": to_state,
            "trigger": "turn.started",
            "updated_at": "2026-02-24T00:00:00",
            "pending_interaction_id": None,
        },
        "meta": {"attempt": attempt},
    }


def test_protocol_history_partitioned_by_attempt(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    (audit_dir / "meta.2.json").write_text("{}", encoding="utf-8")
    (audit_dir / "fcmp_events.1.jsonl").write_text(
        json.dumps(_fcmp_state_event(seq=1, attempt=1, to_state="running")) + "\n",
        encoding="utf-8",
    )
    (audit_dir / "fcmp_events.2.jsonl").write_text(
        json.dumps(_fcmp_state_event(seq=1, attempt=2, to_state="waiting_user")) + "\n",
        encoding="utf-8",
    )
    (audit_dir / "events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "events.2.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "orchestrator_events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "orchestrator_events.2.jsonl").write_text("", encoding="utf-8")

    service = RunObservabilityService()
    monkeypatch.setattr(
        service,
        "_materialize_protocol_stream",
        lambda **_kwargs: {"rasp_events": [], "fcmp_events": []},
    )
    monkeypatch.setattr(
        service,
        "_read_status_payload",
        lambda _run_dir: {"status": "succeeded"},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request",
        lambda _request_id: {"runtime_options": {"execution_mode": "interactive"}, "engine": "codex"},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_interaction_count",
        lambda _request_id: 1,
    )

    payload_attempt_1 = service.list_protocol_history(
        run_dir=run_dir,
        request_id="req-1",
        stream="fcmp",
        attempt=1,
    )
    assert payload_attempt_1["attempt"] == 1
    assert payload_attempt_1["available_attempts"] == [1, 2]
    assert payload_attempt_1["events"][0]["meta"]["attempt"] == 1

    payload_attempt_2 = service.list_protocol_history(
        run_dir=run_dir,
        request_id="req-1",
        stream="fcmp",
        attempt=2,
    )
    assert payload_attempt_2["attempt"] == 2
    assert payload_attempt_2["available_attempts"] == [1, 2]
    assert payload_attempt_2["events"][0]["meta"]["attempt"] == 2
