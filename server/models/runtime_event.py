"""Runtime protocol and orchestration event models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RuntimeEventCategory(str, Enum):
    """Top-level category for runtime protocol events."""

    LIFECYCLE = "lifecycle"
    AGENT = "agent"
    INTERACTION = "interaction"
    TOOL = "tool"
    ARTIFACT = "artifact"
    DIAGNOSTIC = "diagnostic"
    RAW = "raw"


class RuntimeEventSource(BaseModel):
    """Source metadata for a runtime event."""

    engine: str
    parser: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RuntimeEventRef(BaseModel):
    """Byte-level reference back to raw stream evidence."""

    attempt_number: int = Field(ge=1)
    stream: str
    byte_from: int = Field(ge=0)
    byte_to: int = Field(ge=0)
    encoding: str = "utf-8"


class RuntimeEventIdentity(BaseModel):
    """Event semantic identity."""

    category: RuntimeEventCategory
    type: str


class RuntimeEventEnvelope(BaseModel):
    """RASP/1.0 event envelope."""

    protocol_version: str = "rasp/1.0"
    run_id: str
    seq: int = Field(ge=1)
    ts: datetime
    source: RuntimeEventSource
    event: RuntimeEventIdentity
    data: Dict[str, Any] = Field(default_factory=dict)
    correlation: Dict[str, Any] = Field(default_factory=dict)
    attempt_number: int = Field(ge=1)
    raw_ref: Optional[RuntimeEventRef] = None


class ConversationEventEnvelope(BaseModel):
    """FCMP/1.0 event envelope."""

    protocol_version: str = "fcmp/1.0"
    run_id: str
    seq: int = Field(ge=1)
    ts: datetime
    engine: str
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    raw_ref: Optional[RuntimeEventRef] = None


class FcmpEventType(str, Enum):
    """Canonical FCMP event type names for public stream contracts."""

    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_STATE_CHANGED = "conversation.state.changed"
    ASSISTANT_MESSAGE_FINAL = "assistant.message.final"
    USER_INPUT_REQUIRED = "user.input.required"
    INTERACTION_REPLY_ACCEPTED = "interaction.reply.accepted"
    INTERACTION_AUTO_DECIDE_TIMEOUT = "interaction.auto_decide.timeout"
    CONVERSATION_COMPLETED = "conversation.completed"
    CONVERSATION_FAILED = "conversation.failed"
    DIAGNOSTIC_WARNING = "diagnostic.warning"
    RAW_STDOUT = "raw.stdout"
    RAW_STDERR = "raw.stderr"


class OrchestratorEventType(str, Enum):
    """Canonical orchestrator event names persisted to audit trail."""

    LIFECYCLE_RUN_STARTED = "lifecycle.run.started"
    LIFECYCLE_RUN_TERMINAL = "lifecycle.run.terminal"
    LIFECYCLE_RUN_CANCELED = "lifecycle.run.canceled"
    INTERACTION_USER_INPUT_REQUIRED = "interaction.user_input.required"
    ERROR_RUN_FAILED = "error.run.failed"
    DIAGNOSTIC_WARNING = "diagnostic.warning"


class InteractionHistoryEventType(str, Enum):
    """Interaction history event names persisted in run store."""

    ASK_USER = "ask_user"
    REPLY = "reply"


class InteractiveResolutionMode(str, Enum):
    """Resolution mode for resume command and reply history."""

    USER_REPLY = "user_reply"
    AUTO_DECIDE_TIMEOUT = "auto_decide_timeout"
