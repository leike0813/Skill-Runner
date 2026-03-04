"""Current run projection and terminal result models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .common import ClientConversationMode, ExecutionMode, RunStatus
from .interaction import PendingOwner, ResumeCause


class CurrentRunProjection(BaseModel):
    """Single source of truth for non-historical run state."""

    request_id: str
    run_id: str
    status: RunStatus
    updated_at: datetime
    current_attempt: int = Field(default=1, ge=1)
    pending_owner: Optional[PendingOwner] = None
    pending_interaction_id: Optional[int] = None
    pending_auth_session_id: Optional[str] = None
    resume_ticket_id: Optional[str] = None
    resume_cause: Optional[ResumeCause] = None
    source_attempt: Optional[int] = Field(default=None, ge=1)
    target_attempt: Optional[int] = Field(default=None, ge=1)
    conversation_mode: Optional[ClientConversationMode] = None
    requested_execution_mode: Optional[ExecutionMode] = None
    effective_execution_mode: Optional[ExecutionMode] = None
    effective_interactive_require_user_reply: Optional[bool] = None
    effective_interactive_reply_timeout_sec: Optional[int] = Field(default=None, ge=0)
    effective_session_timeout_sec: Optional[int] = Field(default=None, ge=1)
    error: Optional[Any] = None
    warnings: List[Any] = Field(default_factory=list)


class TerminalRunResult(BaseModel):
    """Terminal-only result envelope."""

    status: Literal["success", "succeeded", "failed", "canceled"]
    data: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)
    repair_level: str = "none"
    validation_warnings: List[str] = Field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
