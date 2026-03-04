from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from server.models import RunStatus
from server.services.orchestration.run_audit_service import RunAuditService


def test_write_attempt_audit_artifacts_persists_auth_detection_and_diagnostic(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-auth-audit"
    run_dir.mkdir(parents=True, exist_ok=True)
    service = RunAuditService()
    service.write_attempt_audit_artifacts(
        run_dir=run_dir,
        run_id="run-auth-audit",
        request_id="req-auth-audit",
        engine_name="opencode",
        execution_mode="interactive",
        attempt_number=1,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        status=RunStatus.FAILED,
        fs_before_snapshot={},
        process_exit_code=1,
        process_failure_reason="AUTH_REQUIRED",
        process_raw_stdout="",
        process_raw_stderr='{"type":"error"}',
        adapter=None,
        turn_payload={},
        validation_warnings=[],
        terminal_error_code="AUTH_REQUIRED",
        options={},
        auth_detection={
            "classification": "auth_required",
            "subcategory": "invalid_api_key",
            "confidence": "high",
            "engine": "opencode",
            "provider_id": "deepseek",
            "matched_rule_ids": ["opencode_invalid_api_key_from_message"],
            "evidence_sources": ["stdout_text", "structured_ndjson"],
            "evidence_excerpt": "Invalid API key",
            "details": {"extracted": {"message": "Invalid API key"}},
        },
    )

    audit_dir = run_dir / ".audit"
    meta_payload = json.loads((audit_dir / "meta.1.json").read_text(encoding="utf-8"))
    assert meta_payload["auth_detection"]["classification"] == "auth_required"
    assert meta_payload["auth_detection"]["subcategory"] == "invalid_api_key"

    diagnostics_rows = [
        json.loads(line)
        for line in (audit_dir / "parser_diagnostics.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert diagnostics_rows
    assert diagnostics_rows[0]["data"]["code"] == "AUTH_DETECTION_MATCHED"
    assert diagnostics_rows[0]["data"]["confidence"] == "high"
