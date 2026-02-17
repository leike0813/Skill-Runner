"""
Data Models for Skill Runner.

This module defines the core Pydantic models used throughout the application
for validation, serialization, and type hinting. It covers:
- Run lifecycle states (RunStatus)
- Skill Manifest definitions (SkillManifest)
- API Request/Response schemas (RunCreateRequest, RunResponse)
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from pathlib import Path

class RunStatus(str, Enum):
    """
    Enum representing the lifecycle state of an execution run.
    """
    QUEUED = "queued"       # Request received, waiting for orchestrator
    RUNNING = "running"     # Active execution in progress
    WAITING_USER = "waiting_user"  # Waiting for user interaction reply
    SUCCEEDED = "succeeded" # Finished successfully (exit code 0)
    FAILED = "failed"       # Finished with error or non-zero exit code
    CANCELED = "canceled"   # Terminated by user or timeout


class ExecutionMode(str, Enum):
    """Execution strategy for run orchestration."""
    AUTO = "auto"
    INTERACTIVE = "interactive"


class EngineSessionHandleType(str, Enum):
    """Normalized engine session handle type."""
    SESSION_ID = "session_id"
    SESSION_FILE = "session_file"
    OPAQUE = "opaque"


class EngineInteractiveProfileKind(str, Enum):
    """Interactive execution tier chosen by capability probe."""
    RESUMABLE = "resumable"
    STICKY_PROCESS = "sticky_process"


class InteractiveErrorCode(str, Enum):
    """Stable error codes for interactive execution."""
    SESSION_RESUME_FAILED = "SESSION_RESUME_FAILED"
    INTERACTION_WAIT_TIMEOUT = "INTERACTION_WAIT_TIMEOUT"
    INTERACTION_PROCESS_LOST = "INTERACTION_PROCESS_LOST"
    ORCHESTRATOR_RESTART_INTERRUPTED = "ORCHESTRATOR_RESTART_INTERRUPTED"


class RecoveryState(str, Enum):
    """Run recovery state after orchestrator startup reconciliation."""
    NONE = "none"
    RECOVERED_WAITING = "recovered_waiting"
    FAILED_RECONCILED = "failed_reconciled"


class AdapterTurnOutcome(str, Enum):
    """Normalized engine turn outcome for orchestrator consumption."""
    FINAL = "final"
    ASK_USER = "ask_user"
    ERROR = "error"


class EngineSessionHandle(BaseModel):
    """Opaque session handle persisted for resumable engines."""
    engine: str
    handle_type: EngineSessionHandleType
    handle_value: str
    created_at_turn: int = 1


class EngineResumeCapability(BaseModel):
    """Result of engine resume capability probing."""
    supported: bool
    probe_method: str = "command"
    detail: str = ""


class EngineInteractiveProfile(BaseModel):
    """Resolved execution profile for interactive runs."""
    kind: EngineInteractiveProfileKind
    reason: str = ""
    session_timeout_sec: int = Field(default=1200, ge=1)


class SkillInstallStatus(str, Enum):
    """Lifecycle state for async skill package install requests."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class ManifestArtifact(BaseModel):
    """
    Defines an expected output artifact from a skill execution.
    Used for runtime redirection and validation.
    """
    role: str
    """Logical name/role of the artifact (e.g., 'final_report', 'data_csv')."""
    
    pattern: str
    """Glob pattern or filename to match in the output (e.g., 'report.md')."""
    
    mime: Optional[str] = None
    """Optional MIME type for the artifact."""
    
    required: bool = False
    """If True, execution is marked failed if this artifact is missing."""

class RuntimeDefinition(BaseModel):
    """
    Defines the runtime environment requirements for a skill.
    """
    language: str = "python"
    """Programming language (currently primarily 'python')."""
    
    version: str = "3.11"
    """Language version constraint."""
    
    dependencies: List[str] = []
    """List of PyPI dependencies to install via `uv`."""

class SkillManifest(BaseModel):
    """
    Represents the metadata and configuration of a registered Skill.
    Loaded from `runner.json` or `SKILL.md` frontmatter.
    """
    id: str
    """Unique identifier for the skill (folder name)."""
    
    path: Optional[Path] = None
    """Absolute filesystem path to the skill directory."""
    
    version: str = "1.0.0"
    """Semantic version of the skill."""
    
    name: Optional[str] = None
    """Human-readable display name."""
    
    description: Optional[str] = None
    """Brief description of the skill's capability."""
    
    engines: List[str] = []
    """List of supported engines (e.g., ['gemini', 'codex'])."""

    execution_modes: List[ExecutionMode] = Field(default_factory=lambda: [ExecutionMode.AUTO])
    """Allowed execution modes for this skill."""
    
    entrypoint: Optional[Dict[str, Any]] = {} 
    """
    Execution entrypoint configuration.
    Example: {"prompts": {"gemini": "..."}} or {"script": "run.py"}
    """
    
    artifacts: List[ManifestArtifact] = []
    """List of expected output artifacts."""
    
    schemas: Optional[Dict[str, str]] = {}
    """Paths to JSON schemas for validation (e.g., {'input': 'assets/input.json'})."""
    
    runtime: Optional[RuntimeDefinition] = None
    """Runtime environment requirements."""

class RunCreateRequest(BaseModel):
    """
    Payload for creating a new execution job via POST /jobs.
    """
    skill_id: str
    """ID of the skill to execute."""
    
    engine: str = "codex"
    """Target execution engine (default: 'codex')."""

    input: Dict[str, Any] = {}
    """Business input payload (inline input values). File inputs still come from uploads/."""
    
    parameter: Dict[str, Any] = {}
    """Key-value pairs for template substitution (parameters)."""

    model: Optional[str] = None
    """Engine model specification (e.g., gemini-2.5-pro or gpt-5.2-codex@high)."""

    runtime_options: Dict[str, Any] = {}
    """Runtime-only options (do not affect output)."""


class RunCreateResponse(BaseModel):
    """
    Response for creating a run request.
    """
    request_id: str
    """ID of the request staging record."""

    cache_hit: bool = False
    """Whether a cached result was returned."""

    status: Optional[RunStatus] = None
    """Run status if available."""


class RunUploadResponse(BaseModel):
    """
    Response for uploading input files for a request.
    """
    request_id: str
    """ID of the request staging record."""

    cache_hit: bool = False
    """Whether a cached result was returned."""

    extracted_files: List[str] = []
    """List of files extracted from the upload."""


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
    status: RunStatus
    extracted_files: List[str] = []

class RequestStatusResponse(BaseModel):
    """
    Response payload for request status.
    """
    request_id: str
    """Request identifier."""

    status: RunStatus
    """Current status of the run."""

    skill_id: str
    """ID of the executed skill."""

    engine: str
    """Engine used for execution."""

    created_at: datetime
    """Timestamp of run creation."""

    updated_at: datetime
    """Timestamp of last status update."""

    warnings: List[Any] = []
    """List of non-blocking warnings encountered during setup/execution."""

    error: Optional[Any] = None
    """Error details if status is FAILED."""

    auto_decision_count: int = 0
    """Number of timeout-triggered automatic interaction decisions."""

    last_auto_decision_at: Optional[datetime] = None
    """Timestamp of the latest timeout-triggered automatic interaction decision."""

    pending_interaction_id: Optional[int] = None
    """Current pending interaction id when status is waiting_user."""

    interaction_count: int = 0
    """Total interaction rounds already recorded for this request."""

    recovery_state: RecoveryState = RecoveryState.NONE
    """Startup recovery outcome for this run."""

    recovered_at: Optional[datetime] = None
    """Timestamp when startup reconciliation was applied."""

    recovery_reason: Optional[str] = None
    """Human-readable reason for startup reconciliation decision."""

class RunResponse(BaseModel):
    """
    Internal response format for run status snapshots.
    """
    run_id: str
    """Unique UUID for the run instance."""
    
    status: RunStatus
    """Current status of the run."""
    
    skill_id: str
    """ID of the executed skill."""
    
    engine: str
    """Engine used for execution."""
    
    created_at: datetime
    """Timestamp of run creation."""
    
    updated_at: datetime
    """Timestamp of last status update."""
    
    warnings: List[Any] = []
    """List of non-blocking warnings encountered during setup/execution."""
    
    error: Optional[Any] = None
    """Error details if status is FAILED."""

class EngineInfo(BaseModel):
    """
    Basic engine info returned by the engine registry.
    """
    engine: str
    """Engine identifier (codex/gemini/iflow)."""

    cli_version_detected: Optional[str] = None
    """Detected CLI version, if available."""

class EnginesResponse(BaseModel):
    """
    Response payload listing available engines.
    """
    engines: List[EngineInfo]

class EngineModelInfo(BaseModel):
    """
    Model entry returned by the engine registry.
    """
    id: str
    """Model identifier."""

    display_name: Optional[str] = None
    """Human-friendly model name."""

    deprecated: bool = False
    """Whether the model is deprecated."""

    notes: Optional[str] = None
    """Optional notes or labels for the model."""

    supported_effort: Optional[List[str]] = None
    """Supported reasoning effort levels (Codex only)."""

class EngineModelsResponse(BaseModel):
    """
    Response payload listing models for a specific engine.
    """
    engine: str
    """Engine identifier."""

    cli_version_detected: Optional[str] = None
    """Detected CLI version, if available."""

    snapshot_version_used: str
    """Pinned snapshot version used for the response."""

    source: str
    """Snapshot source type."""

    fallback_reason: Optional[str] = None
    """Reason for snapshot fallback, if any."""

    models: List[EngineModelInfo]


class EngineAuthStatusResponse(BaseModel):
    """Response payload for engine authentication observability."""
    engines: Dict[str, Dict[str, Any]]


class EngineUpgradeTaskStatus(str, Enum):
    """Lifecycle state for engine upgrade tasks."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EngineUpgradeCreateRequest(BaseModel):
    """Request payload for creating an engine upgrade task."""
    mode: str
    engine: Optional[str] = None


class EngineUpgradeCreateResponse(BaseModel):
    """Response payload for created engine upgrade task."""
    request_id: str
    status: EngineUpgradeTaskStatus


class EngineUpgradeEngineResult(BaseModel):
    """Per-engine execution output for upgrade tasks."""
    status: str
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


class EngineUpgradeStatusResponse(BaseModel):
    """Response payload for engine upgrade task status."""
    request_id: str
    mode: str
    requested_engine: Optional[str] = None
    status: EngineUpgradeTaskStatus
    results: Dict[str, EngineUpgradeEngineResult]
    created_at: datetime
    updated_at: datetime


class EngineManifestModelInfo(BaseModel):
    """Model entry in manifest management view."""
    id: str
    display_name: Optional[str] = None
    deprecated: bool = False
    notes: Optional[str] = None
    supported_effort: Optional[List[str]] = None


class EngineManifestViewResponse(BaseModel):
    """Response payload for engine manifest view."""
    engine: str
    cli_version_detected: Optional[str] = None
    manifest: Dict[str, Any]
    resolved_snapshot_version: str
    resolved_snapshot_file: str
    fallback_reason: Optional[str] = None
    models: List[EngineManifestModelInfo]


class EngineSnapshotCreateModel(BaseModel):
    """Payload item for creating a model snapshot."""
    id: str
    display_name: Optional[str] = None
    deprecated: bool = False
    notes: Optional[str] = None
    supported_effort: Optional[List[str]] = None


class EngineSnapshotCreateRequest(BaseModel):
    """Request payload for creating a model snapshot for detected version."""
    models: List[EngineSnapshotCreateModel] = Field(min_length=1)

class RunResultResponse(BaseModel):
    """
    Response payload for run results.
    """
    request_id: str
    """Request identifier."""

    result: Dict[str, Any]
    """Normalized result payload."""

class RunArtifactsResponse(BaseModel):
    """
    Response payload listing artifacts for a run.
    """
    request_id: str
    """Request identifier."""

    artifacts: List[str]
    """Artifact paths relative to the run directory."""

class RunLogsResponse(BaseModel):
    """
    Response payload containing run logs.
    """
    request_id: str
    """Request identifier."""

    prompt: Optional[str] = None
    """Prompt text used for the run."""

    stdout: Optional[str] = None
    """Captured stdout output."""

    stderr: Optional[str] = None
    """Captured stderr output."""


class InteractionKind(str, Enum):
    """Classifies why agent asks user input."""
    CHOOSE_ONE = "choose_one"
    CONFIRM = "confirm"
    FILL_FIELDS = "fill_fields"
    OPEN_TEXT = "open_text"
    RISK_ACK = "risk_ack"


class InteractionOption(BaseModel):
    """Selectable choice in pending interaction."""
    label: str
    value: Any


class AdapterTurnInteraction(BaseModel):
    """Structured interaction payload returned by adapters."""
    interaction_id: int = Field(ge=1)
    kind: InteractionKind = InteractionKind.OPEN_TEXT
    prompt: str
    options: List[InteractionOption] = Field(default_factory=list)
    ui_hints: Dict[str, Any] = Field(default_factory=dict)
    default_decision_policy: str = "engine_judgement"
    required_fields: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


class AdapterTurnResult(BaseModel):
    """Unified turn protocol returned by adapters."""
    outcome: AdapterTurnOutcome
    final_data: Optional[Dict[str, Any]] = None
    interaction: Optional[AdapterTurnInteraction] = None
    stderr: Optional[str] = None
    repair_level: str = "none"
    failure_reason: Optional[str] = None


class PendingInteraction(BaseModel):
    """Pending interaction payload returned to clients."""
    interaction_id: int
    kind: InteractionKind
    prompt: str
    options: List[InteractionOption] = Field(default_factory=list)
    ui_hints: Dict[str, Any] = Field(default_factory=dict)
    default_decision_policy: str = "engine_judgement"
    required_fields: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


class InteractionPendingResponse(BaseModel):
    """Response payload for pending interaction query."""
    request_id: str
    status: RunStatus
    pending: Optional[PendingInteraction] = None


class InteractionReplyRequest(BaseModel):
    """Request payload for interaction reply submission."""
    interaction_id: int
    response: Any
    idempotency_key: Optional[str] = None


class InteractionReplyResponse(BaseModel):
    """Response payload for interaction reply acceptance."""
    request_id: str
    status: RunStatus
    accepted: bool


class CancelResponse(BaseModel):
    """Response payload for run cancellation requests."""
    request_id: str
    run_id: str
    status: RunStatus
    accepted: bool
    message: str


class ManagementSkillSummary(BaseModel):
    """Frontend-friendly skill summary used by management API."""
    id: str
    name: str
    version: str
    engines: List[str] = []
    installed_at: Optional[datetime] = None
    health: str = "healthy"
    health_error: Optional[str] = None


class ManagementSkillDetail(ManagementSkillSummary):
    """Skill detail payload used by management API."""
    schemas: Dict[str, str] = {}
    entrypoints: Dict[str, Any] = {}
    files: List[Dict[str, Any]] = []


class ManagementSkillListResponse(BaseModel):
    """Response payload for management skill list."""
    skills: List[ManagementSkillSummary] = []


class ManagementEngineSummary(BaseModel):
    """Frontend-friendly engine summary used by management API."""
    engine: str
    cli_version: Optional[str] = None
    auth_ready: bool = False
    sandbox_status: str = "unknown"
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


class ManagementRunListResponse(BaseModel):
    """Response payload for management run list."""
    runs: List[ManagementRunConversationState] = []


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


class RunCleanupResponse(BaseModel):
    """
    Response payload for manual cleanup actions.
    """
    runs_deleted: int
    """Number of run records deleted."""

    requests_deleted: int
    """Number of request records deleted."""

    cache_entries_deleted: int
    """Number of cache entries deleted."""


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

class ErrorResponse(BaseModel):
    """
    Standard API Error response structure.
    """
    code: str
    """Machine-readable error code."""
    
    message: str
    """Human-readable error message."""
    
    details: Optional[Dict[str, Any]] = None
    """Additional debugging context."""
    
    request_id: Optional[str] = None
    """Associated request ID if applicable."""
