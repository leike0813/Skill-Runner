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
    correlation: Dict[str, Any] = Field(default_factory=dict)
    raw_ref: Optional[RuntimeEventRef] = None


class ChatReplayRole(str, Enum):
    """Canonical chat replay role names for UI-facing chat bubbles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatReplayKind(str, Enum):
    """Canonical chat replay semantic kinds."""

    INTERACTION_REPLY = "interaction_reply"
    AUTH_SUBMISSION = "auth_submission"
    ASSISTANT_PROCESS = "assistant_process"
    ASSISTANT_FINAL = "assistant_final"
    ORCHESTRATION_NOTICE = "orchestration_notice"


class ChatReplayEventEnvelope(BaseModel):
    """Chat replay envelope used as canonical chat bubble SSOT."""

    protocol_version: str = "chat-replay/1.0"
    run_id: str
    seq: int = Field(ge=1)
    created_at: datetime
    attempt: int = Field(ge=1)
    role: ChatReplayRole
    kind: ChatReplayKind
    text: str = Field(min_length=1)
    correlation: Dict[str, Any] = Field(default_factory=dict)


class FcmpEventType(str, Enum):
    """Canonical FCMP event type names for public stream contracts."""

    CONVERSATION_STATE_CHANGED = "conversation.state.changed"
    ASSISTANT_REASONING = "assistant.reasoning"
    ASSISTANT_TOOL_CALL = "assistant.tool_call"
    ASSISTANT_COMMAND_EXECUTION = "assistant.command_execution"
    ASSISTANT_MESSAGE_PROMOTED = "assistant.message.promoted"
    ASSISTANT_MESSAGE_FINAL = "assistant.message.final"
    USER_INPUT_REQUIRED = "user.input.required"
    AUTH_REQUIRED = "auth.required"
    AUTH_CHALLENGE_UPDATED = "auth.challenge.updated"
    AUTH_INPUT_ACCEPTED = "auth.input.accepted"
    AUTH_COMPLETED = "auth.completed"
    AUTH_FAILED = "auth.failed"
    INTERACTION_REPLY_ACCEPTED = "interaction.reply.accepted"
    INTERACTION_AUTO_DECIDE_TIMEOUT = "interaction.auto_decide.timeout"
    DIAGNOSTIC_WARNING = "diagnostic.warning"
    RAW_STDOUT = "raw.stdout"
    RAW_STDERR = "raw.stderr"


class OrchestratorEventType(str, Enum):
    """Canonical orchestrator event names persisted to audit trail."""

    LIFECYCLE_RUN_STARTED = "lifecycle.run.started"
    LIFECYCLE_RUN_TERMINAL = "lifecycle.run.terminal"
    LIFECYCLE_RUN_CANCELED = "lifecycle.run.canceled"
    INTERACTION_USER_INPUT_REQUIRED = "interaction.user_input.required"
    INTERACTION_REPLY_ACCEPTED = "interaction.reply.accepted"
    AUTH_METHOD_SELECTION_REQUIRED = "auth.method.selection.required"
    AUTH_METHOD_SELECTED = "auth.method.selected"
    AUTH_SESSION_CREATED = "auth.session.created"
    AUTH_CHALLENGE_UPDATED = "auth.challenge.updated"
    AUTH_INPUT_ACCEPTED = "auth.input.accepted"
    AUTH_SESSION_COMPLETED = "auth.session.completed"
    AUTH_SESSION_FAILED = "auth.session.failed"
    AUTH_SESSION_TIMED_OUT = "auth.session.timed_out"
    AUTH_SESSION_BUSY = "auth.session.busy"
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
