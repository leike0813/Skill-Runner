"""Current run state envelopes persisted under .state/."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import ClientConversationMode, DispatchPhase, ExecutionMode, RunStatus
from .interaction import PendingOwner, ResumeCause


class RunStatePhase(BaseModel):
    """Internal phases that refine the top-level runtime state."""

    waiting_auth_phase: Optional[str] = None
    dispatch_phase: Optional[DispatchPhase] = None


class RunPendingState(BaseModel):
    """Current waiting payload embedded into .state/state.json."""

    owner: Optional[PendingOwner] = None
    interaction_id: Optional[int] = Field(default=None, ge=1)
    auth_session_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class RunResumeState(BaseModel):
    """Resume ownership metadata for queued/resumed attempts."""

    resume_ticket_id: Optional[str] = None
    resume_cause: Optional[ResumeCause] = None
    source_attempt: Optional[int] = Field(default=None, ge=1)
    target_attempt: Optional[int] = Field(default=None, ge=1)


class RunRuntimeState(BaseModel):
    """Effective runtime policy embedded into current state."""

    conversation_mode: Optional[ClientConversationMode] = None
    requested_execution_mode: Optional[ExecutionMode] = None
    effective_execution_mode: Optional[ExecutionMode] = None
    effective_interactive_require_user_reply: Optional[bool] = None
    effective_interactive_reply_timeout_sec: Optional[int] = Field(default=None, ge=0)
    effective_session_timeout_sec: Optional[int] = Field(default=None, ge=1)


class RunStateEnvelope(BaseModel):
    """Single current-truth envelope persisted under .state/state.json."""

    request_id: str
    run_id: str
    status: RunStatus
    updated_at: datetime
    current_attempt: int = Field(default=1, ge=0)
    state_phase: RunStatePhase = Field(default_factory=RunStatePhase)
    pending: RunPendingState = Field(default_factory=RunPendingState)
    resume: RunResumeState = Field(default_factory=RunResumeState)
    runtime: RunRuntimeState = Field(default_factory=RunRuntimeState)
    error: Optional[Any] = None
    warnings: List[Any] = Field(default_factory=list)
