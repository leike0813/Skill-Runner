"""Common enums and shared models."""

from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Enum representing the lifecycle state of an execution run."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class ExecutionMode(str, Enum):
    """Execution strategy for run orchestration."""

    AUTO = "auto"
    INTERACTIVE = "interactive"


class EngineSessionHandleType(str, Enum):
    """Normalized engine session handle type."""

    SESSION_ID = "session_id"
    SESSION_FILE = "session_file"
    OPAQUE = "opaque"


class InteractiveErrorCode(str, Enum):
    """Stable error codes for interactive execution."""

    SESSION_RESUME_FAILED = "SESSION_RESUME_FAILED"
    INTERACTIVE_MAX_ATTEMPT_EXCEEDED = "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
    ORCHESTRATOR_RESTART_INTERRUPTED = "ORCHESTRATOR_RESTART_INTERRUPTED"
    PROTOCOL_SCHEMA_VIOLATION = "PROTOCOL_SCHEMA_VIOLATION"


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
    """Single resumable session configuration for interactive runs."""

    reason: str = ""
    session_timeout_sec: int = Field(default=1200, ge=1)


class SkillInstallStatus(str, Enum):
    """Lifecycle state for async skill package install requests."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
