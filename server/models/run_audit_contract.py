"""Attempt-scoped audit artifact contract models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AttemptAuditMeta(BaseModel):
    request_id: str
    run_id: str
    attempt_number: int = Field(ge=1)
    created_at: datetime
    status: str
    engine: Optional[str] = None
    skill_id: Optional[str] = None


class RunAuditContract(BaseModel):
    request_id: str
    run_id: str
    attempt_number: int = Field(ge=1)
    request_input_path: str | None = None
    run_service_log_path: str | None = None
    meta_path: str
    orchestrator_events_path: str
    output_repair_path: str
    events_path: str
    fcmp_events_path: str
    service_log_path: str | None = None
    stdin_path: str | None = None
    stdout_path: str
    stderr_path: str
    io_chunks_path: str
    pty_output_path: str
    fs_before_path: str | None = None
    fs_after_path: str | None = None
    fs_diff_path: str | None = None
    parser_diagnostics_path: str
    protocol_metrics_path: str
