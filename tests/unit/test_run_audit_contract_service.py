from __future__ import annotations

from pathlib import Path

from server.services.orchestration.run_audit_contract_service import run_audit_contract_service


def test_initialize_attempt_audit_creates_service_log_skeleton(tmp_path: Path):
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)

    run_audit_contract_service.initialize_run_audit(run_dir=run_dir)
    run_audit_contract_service.initialize_attempt_audit(
        run_dir=run_dir,
        request_id="req-1",
        attempt_number=1,
        status="queued",
        engine="codex",
        skill_id="skill-1",
    )

    run_service_log_path = run_dir / ".audit" / "service.run.log"
    service_log_path = run_dir / ".audit" / "service.1.log"
    assert run_service_log_path.exists()
    assert run_service_log_path.read_text(encoding="utf-8") == ""
    assert service_log_path.exists()
    assert service_log_path.read_text(encoding="utf-8") == ""
