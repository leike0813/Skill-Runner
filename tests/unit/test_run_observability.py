import json
from pathlib import Path

from server.services.run_observability import RunObservabilityService


def test_list_runs_and_get_logs_tail(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("line1\nline2\n", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("err1\n", encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}), encoding="utf-8")

    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_requests_with_runs",
        lambda limit=200: [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo",
                "engine": "gemini",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request_with_run",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-1",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "running",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    service = RunObservabilityService()
    rows = service.list_runs()
    assert len(rows) == 1
    assert rows[0]["request_id"] == "req-1"
    assert rows[0]["status"] == "running"

    tail = service.get_logs_tail("req-1", max_bytes=5)
    assert tail["poll"] is True
    assert tail["stdout"].endswith("ne2\n")
    assert "err1" in tail["stderr"]
