"""Dispatch-state envelope persisted under .state/dispatch.json."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .common import DispatchPhase


class RunDispatchEnvelope(BaseModel):
    """Durable queued-state dispatch lifecycle."""

    request_id: str
    run_id: str
    dispatch_ticket_id: str
    phase: DispatchPhase
    worker_claim_id: Optional[str] = None
    admitted_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    updated_at: datetime
