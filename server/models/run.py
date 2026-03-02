"""Run/request/result domain models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .common import RecoveryState, RunStatus, SkillInstallStatus


class RunCreateRequest(BaseModel):
    """Payload for creating a new execution job via POST /jobs."""

    skill_id: str
    engine: str = "codex"
    input: Dict[str, Any] = {}
    parameter: Dict[str, Any] = {}
    model: Optional[str] = None
    runtime_options: Dict[str, Any] = {}


class RunCreateResponse(BaseModel):
    """Response for creating a run request."""

    request_id: str
    cache_hit: bool = False
    status: Optional[RunStatus] = None


class RunUploadResponse(BaseModel):
    """Response for uploading input files for a request."""

    request_id: str
    cache_hit: bool = False
    extracted_files: List[str] = []


class TempSkillRunCreateRequest(BaseModel):
    """Payload for creating a temporary skill run request."""

    engine: str = "codex"
    parameter: Dict[str, Any] = {}
    model: Optional[str] = None
    runtime_options: Dict[str, Any] = {}


class TempSkillRunCreateResponse(BaseModel):
    """Response for temporary skill run request creation."""

    request_id: str
    status: RunStatus


class TempSkillRunUploadResponse(BaseModel):
    """Response for temporary skill package/input upload."""

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
    interaction_count: int = 0
    recovery_state: RecoveryState = RecoveryState.NONE
    recovered_at: Optional[datetime] = None
    recovery_reason: Optional[str] = None
    interactive_auto_reply: Optional[bool] = None
    interactive_reply_timeout_sec: Optional[int] = None


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
