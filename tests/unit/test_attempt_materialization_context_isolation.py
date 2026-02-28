import json
from pathlib import Path

from server.runtime.observability.run_observability import RunObservabilityService


class _Model:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "json") -> dict:
        assert mode == "json"
        return dict(self._payload)


def test_materialize_uses_attempt_meta_and_attempt_pending(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-materialize-context"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "pty-output.1.log").write_text("", encoding="utf-8")
    (audit_dir / "orchestrator_events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text(
        json.dumps(
            {
                "status": "waiting_user",
                "finished_at": "2026-02-24T00:00:10",
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, dict] = {}

    def _build_rasp_events(**kwargs):
        captured["rasp"] = kwargs
        return []

    def _build_fcmp_events(*_args, **kwargs):
        captured["fcmp"] = kwargs
        return [_Model({"protocol_version": "fcmp/1.0", "seq": 1, "meta": {"attempt": 1}, "run_id": "x", "ts": "2026-02-24T00:00:00", "engine": "codex", "type": "conversation.state.changed", "data": {"from": "running", "to": "waiting_user", "trigger": "turn.needs_input", "updated_at": "2026-02-24T00:00:10", "pending_interaction_id": 1}})]

    monkeypatch.setattr("server.runtime.observability.run_observability.build_rasp_events", _build_rasp_events)
    monkeypatch.setattr("server.runtime.observability.run_observability.build_fcmp_events", _build_fcmp_events)
    monkeypatch.setattr("server.runtime.observability.run_observability.compute_protocol_metrics", lambda _rows: {})
    monkeypatch.setattr("server.runtime.observability.run_observability.validate_rasp_event", lambda _row: None)
    monkeypatch.setattr("server.runtime.observability.run_observability.validate_fcmp_event", lambda _row: None)
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        lambda _request_id: {"engine": "codex", "runtime_options": {"execution_mode": "interactive"}},
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        lambda _request_id: [
            {
                "interaction_id": 1,
                "event_type": "ask_user",
                "payload": {"interaction_id": 1, "kind": "open_text", "prompt": "attempt one prompt"},
                "created_at": "2026-02-24T00:00:05",
            }
        ],
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        lambda _request_id: {"interaction_id": 9, "kind": "open_text", "prompt": "latest pending"},
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: 1200,
    )

    service = RunObservabilityService()
    service._materialize_protocol_stream(
        run_dir=run_dir,
        request_id="req-ctx",
        status_payload={"status": "succeeded", "updated_at": "2026-02-24T00:01:00"},
        attempt_number=1,
    )

    assert captured["rasp"]["status"] == "waiting_user"
    assert captured["rasp"]["pending_interaction"]["interaction_id"] == 1
    assert captured["rasp"]["pending_interaction"]["prompt"] == "attempt one prompt"
    assert captured["fcmp"]["status"] == "waiting_user"
    assert captured["fcmp"]["status_updated_at"] == "2026-02-24T00:00:10"
