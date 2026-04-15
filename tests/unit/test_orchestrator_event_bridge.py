from __future__ import annotations

from pathlib import Path

import pytest

from server.models import InteractiveErrorCode
from server.services.orchestration.run_audit_service import RunAuditService


def test_append_orchestrator_event_schema_violation_raises_runtime_error(tmp_path: Path):
    run_dir = tmp_path / "run-schema-error"
    run_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match=InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value):
        RunAuditService().append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=1,
            category="lifecycle",
            type_name="lifecycle.run.started",
            data={"status": "queued"},
        )
