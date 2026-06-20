from __future__ import annotations

from pathlib import Path

import pytest

from server.models import InteractiveErrorCode
from server.services.orchestration.run_audit_service import RunAuditService
from tests.common.workspace_layout_helpers import make_layout


def test_append_orchestrator_event_schema_violation_raises_runtime_error(tmp_path: Path):
    run_dir = tmp_path / "run-schema-error"
    run_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = make_layout(run_dir, namespace="schema-error.1").audit_dir

    with pytest.raises(RuntimeError, match=InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value):
        RunAuditService().append_orchestrator_event(
            run_dir=run_dir,
            audit_dir=audit_dir,
            run_id="run-schema-error",
            attempt_number=1,
            category="lifecycle",
            type_name="lifecycle.run.started",
            data={"status": "queued"},
        )
