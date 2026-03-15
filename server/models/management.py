"""Management API view models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import RecoveryState, RunStatus
from .engine import EngineModelInfo
from .interaction import AskUserHintPayload


class ManagementSkillSummary(BaseModel):
    """Frontend-friendly skill summary used by management API."""

    id: str
    name: str
    description: Optional[str] = None
    version: str
    engines: List[str] = Field(default_factory=list)
    unsupported_engines: List[str] = Field(default_factory=list)
    effective_engines: List[str] = Field(default_factory=list)
    execution_modes: List[str] = Field(default_factory=list)
    is_builtin: bool = False
    installed_at: Optional[datetime] = None
    health: str = "healthy"
    health_error: Optional[str] = None


class ManagementSkillDetail(ManagementSkillSummary):
    """Skill detail payload used by management API."""

    schemas: Dict[str, str] = Field(default_factory=dict)
    entrypoints: Dict[str, Any] = Field(default_factory=dict)
    files: List[Dict[str, Any]] = Field(default_factory=list)


class ManagementSkillSchemasResponse(BaseModel):
    """Skill schema content payload used by management API."""

    skill_id: str
    input: Optional[Dict[str, Any]] = None
    parameter: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None


class ManagementSkillListResponse(BaseModel):
    """Response payload for management skill list."""

    skills: List[ManagementSkillSummary] = Field(default_factory=list)


class ManagementDataResetRequest(BaseModel):
    """Request payload for destructive management data reset."""

    confirmation: str = Field(min_length=1)
    dry_run: bool = False
    include_logs: bool = False
    include_engine_catalog: bool = False
    include_engine_auth_sessions: bool = False


class ManagementDataResetPathResult(BaseModel):
    """Per-target execution result in management data reset response."""

    path: str
    status: str


class ManagementDataResetResponse(BaseModel):
    """Response payload for management data reset operation."""

    dry_run: bool
    data_dir: str
    db_files: List[str] = Field(default_factory=list)
    data_dirs: List[str] = Field(default_factory=list)
    optional_paths: List[str] = Field(default_factory=list)
    recreate_dirs: List[str] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
    deleted_count: int = 0
    missing_count: int = 0
    recreated_count: int = 0
    path_results: List[ManagementDataResetPathResult] = Field(default_factory=list)


class ManagementLoggingEditableSettings(BaseModel):
    """Writable logging settings exposed by management API."""

    model_config = ConfigDict(extra="forbid")

    level: str
    format: str
    retention_days: int = Field(ge=1)
    dir_max_bytes: int = Field(ge=0)


class ManagementLoggingReadonlySettings(BaseModel):
    """Read-only runtime logging inputs exposed by management API."""

    dir: str
    file_basename: str
    rotation_when: str
    rotation_interval: int = Field(ge=1)


class ManagementLoggingSettingsResponse(BaseModel):
    """Full logging settings view with editable and read-only partitions."""

    editable: ManagementLoggingEditableSettings
    read_only: ManagementLoggingReadonlySettings


class ManagementSystemSettingsResponse(BaseModel):
    """Response payload for management system settings."""

    logging: ManagementLoggingSettingsResponse
    engine_auth_session_log_persistence_enabled: bool = False
    reset_confirmation_text: str


class ManagementSystemSettingsUpdateRequest(BaseModel):
    """Update payload for management system settings."""

    model_config = ConfigDict(extra="forbid")

    logging: ManagementLoggingEditableSettings


class ManagementSystemLogItem(BaseModel):
    """Single log row returned by management system log explorer."""

    ts: Optional[str] = None
    level: Optional[str] = None
    message: str
    raw: str
    source: str
    file: str
    line_no: int = Field(ge=1)


class ManagementSystemLogQueryResponse(BaseModel):
    """Cursor-based system log query response for management API."""

    source: str
    items: List[ManagementSystemLogItem] = Field(default_factory=list)
    next_cursor: Optional[int] = Field(default=None, ge=0)
    total_matched: int = Field(default=0, ge=0)


class ManagementEngineAuthImportSpecResponse(BaseModel):
    """Auth import capability spec for one engine/provider."""

    engine: str
    provider_id: Optional[str] = None
    supported: bool = True
    ask_user: Optional[AskUserHintPayload] = None


class ManagementEngineAuthImportSubmitResponse(BaseModel):
    """Auth import submission result."""

    engine: str
    provider_id: Optional[str] = None
    imported_files: List[Dict[str, Any]] = Field(default_factory=list)
    risk_notice_required: bool = False


class ManagementEngineSummary(BaseModel):
    """Frontend-friendly engine summary used by management API."""

    engine: str
    cli_version: Optional[str] = None
    models_count: int = 0


class ManagementEngineDetail(ManagementEngineSummary):
    """Engine detail payload used by management API."""

    models: List[EngineModelInfo] = []
    upgrade_status: Dict[str, Any] = {}
    last_error: Optional[str] = None


class ManagementEngineListResponse(BaseModel):
    """Response payload for management engine list."""

    engines: List[ManagementEngineSummary] = []


class ManagementRunConversationState(BaseModel):
    """Run conversation state for management API."""

    request_id: str
    run_id: str
    status: RunStatus
    engine: str
    model: Optional[str] = None
    skill_id: str
    updated_at: datetime
    pending_interaction_id: Optional[int] = None
    interaction_count: int = 0
    auto_decision_count: int = 0
    last_auto_decision_at: Optional[datetime] = None
    recovery_state: RecoveryState = RecoveryState.NONE
    recovered_at: Optional[datetime] = None
    recovery_reason: Optional[str] = None
    poll_logs: bool = False
    error: Optional[Any] = None
    interactive_auto_reply: Optional[bool] = None
    interactive_reply_timeout_sec: Optional[int] = None


class ManagementRunListResponse(BaseModel):
    """Response payload for management run list."""

    runs: List[ManagementRunConversationState] = []
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    total: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)


class ManagementRunFilesResponse(BaseModel):
    """Response payload for run file tree in management API."""

    request_id: str
    run_id: str
    entries: List[Dict[str, Any]] = []


class ManagementRunFilePreviewResponse(BaseModel):
    """Response payload for run file preview in management API."""

    request_id: str
    run_id: str
    path: str
    preview: Dict[str, Any]
