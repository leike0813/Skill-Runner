import json
from pathlib import Path

from server.runtime.observability.run_observability import RunObservabilityService


def test_list_protocol_history_backfills_orchestrator_seq(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-orchestrator"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-02-24T00:00:00"}),
        encoding="utf-8",
    )
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
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        lambda self, **_kwargs: {"rasp_events": [], "fcmp_events": []},
    )
    service = RunObservabilityService()
    payload = service.list_protocol_history(
        run_dir=run_dir,
        request_id=None,
        stream="orchestrator",
        attempt=1,
    )
    assert payload["attempt"] == 1
    assert [row["seq"] for row in payload["events"]] == [1, 2]
