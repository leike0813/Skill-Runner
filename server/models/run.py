"""Run/request/result domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import (
    ClientConversationMode,
    ClientMetadata,
    DispatchPhase,
    ExecutionMode,
    RecoveryState,
    RunStatus,
    SkillInstallStatus,
)
from .interaction import PendingOwner, ResumeCause


class RequestSkillSource(str, Enum):
    """Request-level skill source for unified /jobs entry."""

    INSTALLED = "installed"
    TEMP_UPLOAD = "temp_upload"


class RunCreateRequest(BaseModel):
    """Payload for creating a new execution job via POST /jobs."""

    skill_source: RequestSkillSource = RequestSkillSource.INSTALLED
    skill_id: Optional[str] = None
    engine: str = "codex"
    input: Dict[str, Any] = {}
    parameter: Dict[str, Any] = {}
    model: Optional[str] = None
    runtime_options: Dict[str, Any] = {}
    client_metadata: ClientMetadata = Field(default_factory=ClientMetadata)


class RunCreateResponse(BaseModel):
    """Response for creating a run request."""

    request_id: str
    cache_hit: bool = False
    status: Optional[RunStatus] = None


class RunUploadResponse(BaseModel):
    """Response for uploading input files for a request."""

    request_id: str
    cache_hit: bool = False
    status: Optional[RunStatus] = None
    extracted_files: List[str] = []


class TempSkillRunCreateRequest(BaseModel):
    """Deprecated temp-skill create payload retained for compatibility in tests/tools."""

    engine: str = "codex"
    parameter: Dict[str, Any] = {}
    model: Optional[str] = None
    runtime_options: Dict[str, Any] = {}
    client_metadata: ClientMetadata = Field(default_factory=ClientMetadata)


class TempSkillRunCreateResponse(BaseModel):
    """Deprecated temp-skill create response."""

    request_id: str
    status: RunStatus


class TempSkillRunUploadResponse(BaseModel):
    """Deprecated temp-skill upload response."""

    request_id: str
    cache_hit: bool = False
    status: RunStatus
    extracted_files: List[str] = []


class RequestStatusResponse(BaseModel):
    """Response payload for request status."""

    request_id: str
    status: RunStatus
    skill_id: str
    engine: str
    created_at: datetime
    updated_at: datetime
    warnings: List[Any] = []
    error: Optional[Any] = None
    auto_decision_count: int = 0
    last_auto_decision_at: Optional[datetime] = None
    pending_interaction_id: Optional[int] = None
    pending_auth_session_id: Optional[str] = None
    pending_payload: Optional[Dict[str, Any]] = None
    interaction_count: int = 0
    recovery_state: RecoveryState = RecoveryState.NONE
    recovered_at: Optional[datetime] = None
    recovery_reason: Optional[str] = None
    requested_execution_mode: Optional[ExecutionMode] = None
    effective_execution_mode: Optional[ExecutionMode] = None
    conversation_mode: Optional[ClientConversationMode] = None
    interactive_auto_reply: Optional[bool] = None
    interactive_reply_timeout_sec: Optional[int] = None
    effective_interactive_require_user_reply: Optional[bool] = None
    effective_interactive_reply_timeout_sec: Optional[int] = None
    current_attempt: Optional[int] = None
    pending_owner: Optional[PendingOwner] = None
    dispatch_phase: Optional[DispatchPhase] = None
    dispatch_ticket_id: Optional[str] = None
    worker_claim_id: Optional[str] = None
    resume_ticket_id: Optional[str] = None
    resume_cause: Optional[ResumeCause] = None
    source_attempt: Optional[int] = None
    target_attempt: Optional[int] = None


class RunResponse(BaseModel):
    """Internal response format for run status snapshots."""

    run_id: str
    status: RunStatus
    skill_id: str
    engine: str
    created_at: datetime
    updated_at: datetime
    warnings: List[Any] = []
    error: Optional[Any] = None


class RunResultResponse(BaseModel):
    """Response payload for run results."""

    request_id: str
    result: Dict[str, Any]


class RunArtifactsResponse(BaseModel):
    """Response payload listing artifacts for a run."""

    request_id: str
    artifacts: List[str]


class RunFileEntry(BaseModel):
    """Run file tree entry for jobs file explorer APIs."""

    path: str
    name: str
    is_dir: bool
    depth: int


class RunFilesResponse(BaseModel):
    """Response payload for run file tree in jobs API."""

    request_id: str
    run_id: str
    entries: List[RunFileEntry] = []


class RunFilePreviewResponse(BaseModel):
    """Response payload for run file preview in jobs API."""

    request_id: str
    run_id: str
    path: str
    preview: Dict[str, Any]


class RunLogsResponse(BaseModel):
    """Response payload containing run logs."""

    request_id: str
    prompt: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class CancelResponse(BaseModel):
    """Response payload for run cancellation requests."""

    request_id: str
    run_id: str
    status: RunStatus
    accepted: bool
    message: str


class RunCleanupResponse(BaseModel):
    """Response payload for manual cleanup actions."""

    runs_deleted: int
    requests_deleted: int
    cache_entries_deleted: int


class SkillInstallCreateResponse(BaseModel):
    """Response for creating a skill package install request."""

    request_id: str
    status: SkillInstallStatus


class SkillInstallStatusResponse(BaseModel):
    """Response payload for skill package install status."""

    request_id: str
    status: SkillInstallStatus
    created_at: datetime
    updated_at: datetime
    skill_id: Optional[str] = None
    version: Optional[str] = None
    action: Optional[str] = None
    error: Optional[str] = None
