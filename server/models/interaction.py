"""Interactive turn and in-conversation auth protocol models."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .common import (
    AdapterTurnOutcome,
    ClientConversationMode,
    ExecutionMode,
    RunStatus,
)


class InteractionKind(str, Enum):
    """Classifies why agent asks user input."""

    CHOOSE_ONE = "choose_one"
    CONFIRM = "confirm"
    FILL_FIELDS = "fill_fields"
    OPEN_TEXT = "open_text"
    UPLOAD_FILES = "upload_files"
    RISK_ACK = "risk_ack"


class InteractionOption(BaseModel):
    """Selectable choice in pending interaction."""

    label: str
    value: Any


class AskUserUploadFileItem(BaseModel):
    """One file selector item for upload_files ask_user hint."""

    name: str
    required: bool = False
    hint: Optional[str] = None
    accept: Optional[str] = None


class AskUserHintPayload(BaseModel):
    """Lightweight optional ask_user hint payload for UI rendering."""

    kind: Literal["open_text", "choose_one", "confirm", "upload_files"] = "open_text"
    prompt: Optional[str] = None
    hint: Optional[str] = None
    options: List[InteractionOption] = Field(default_factory=list)
    files: List[AskUserUploadFileItem] = Field(default_factory=list)
    ui_hints: Dict[str, Any] = Field(default_factory=dict)


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
    source_attempt: int = Field(default=1, ge=1)
    options: List[InteractionOption] = Field(default_factory=list)
    ui_hints: Dict[str, Any] = Field(default_factory=dict)
    default_decision_policy: str = "engine_judgement"
    required_fields: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


class AuthChallengeKind(str, Enum):
    """Supported auth challenge modes surfaced to chat clients."""

    OAUTH_LINK = "oauth_link"
    CALLBACK_URL = "callback_url"
    AUTH_CODE_OR_URL = "auth_code_or_url"
    API_KEY = "api_key"
    BROWSER_CALLBACK_ONLY = "browser_callback_only"
    IMPORT_FILES = "import_files"
    CUSTOM_PROVIDER = "custom_provider"


class AuthMethod(str, Enum):
    """Supported auth methods selectable in waiting_auth."""

    CALLBACK = "callback"
    DEVICE_AUTH = "device_auth"
    AUTH_CODE_OR_URL = "auth_code_or_url"
    API_KEY = "api_key"
    IMPORT = "import"
    CUSTOM_PROVIDER = "custom_provider"


class AuthSessionPhase(str, Enum):
    """Internal phases within waiting_auth."""

    METHOD_SELECTION = "method_selection"
    CHALLENGE_ACTIVE = "challenge_active"


class AuthSubmissionKind(str, Enum):
    """Chat-submitted auth payload kinds."""

    CALLBACK_URL = "callback_url"
    AUTH_CODE_OR_URL = "auth_code_or_url"
    API_KEY = "api_key"
    IMPORT_FILES = "import_files"
    CUSTOM_PROVIDER = "custom_provider"


class ResumeCause(str, Enum):
    """Canonical causes that resume a waiting run."""

    AUTH_COMPLETED = "auth_completed"
    INTERACTION_REPLY = "interaction_reply"
    INTERACTION_AUTO_DECIDE_TIMEOUT = "interaction_auto_decide_timeout"
    RESTART_RECOVERY = "restart_recovery"


class PendingOwner(str, Enum):
    """Current waiting owner for a request."""

    WAITING_USER = "waiting_user"
    WAITING_AUTH_METHOD_SELECTION = "waiting_auth.method_selection"
    WAITING_AUTH_CHALLENGE = "waiting_auth.challenge_active"


class ResumeTicket(BaseModel):
    """Durable request-scoped resume ticket."""

    ticket_id: str
    cause: ResumeCause
    source_attempt: int = Field(ge=1)
    target_attempt: int = Field(ge=1)
    state: Literal["issued", "dispatched", "started"] = "issued"
    created_at: str
    updated_at: str
    dispatched_at: Optional[str] = None
    started_at: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class PendingAuthMethodSelection(BaseModel):
    """Auth method selection payload returned to clients."""

    engine: str
    provider_id: Optional[str] = None
    available_methods: List[AuthMethod] = Field(default_factory=list)
    prompt: str
    instructions: Optional[str] = None
    last_error: Optional[str] = None
    source_attempt: int = Field(default=1, ge=1)
    phase: AuthSessionPhase = AuthSessionPhase.METHOD_SELECTION
    ui_hints: Dict[str, Any] = Field(default_factory=dict)
    ask_user: Optional[AskUserHintPayload] = None


class PendingAuth(BaseModel):
    """Pending auth challenge payload returned to clients."""

    auth_session_id: str
    engine: str
    provider_id: Optional[str] = None
    auth_method: Optional[AuthMethod] = None
    challenge_kind: AuthChallengeKind
    prompt: str
    auth_url: Optional[str] = None
    user_code: Optional[str] = None
    instructions: Optional[str] = None
    accepts_chat_input: bool = False
    input_kind: Optional[AuthSubmissionKind] = None
    last_error: Optional[str] = None
    source_attempt: int = Field(default=1, ge=1)
    phase: AuthSessionPhase = AuthSessionPhase.CHALLENGE_ACTIVE
    timeout_sec: Optional[int] = Field(default=None, ge=1)
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    ask_user: Optional[AskUserHintPayload] = None


class InteractionPendingResponse(BaseModel):
    """Response payload for pending interaction query."""

    request_id: str
    status: RunStatus
    requested_execution_mode: Optional[ExecutionMode] = None
    effective_execution_mode: Optional[ExecutionMode] = None
    conversation_mode: Optional[ClientConversationMode] = None
    effective_interactive_require_user_reply: Optional[bool] = None
    effective_interactive_reply_timeout_sec: Optional[int] = None
    pending: Optional[PendingInteraction] = None
    pending_auth_method_selection: Optional[PendingAuthMethodSelection] = None
    pending_auth: Optional[PendingAuth] = None
    pending_owner: Optional[PendingOwner] = None


class AuthSubmission(BaseModel):
    """Auth payload submitted through the shared chat input channel."""

    kind: AuthSubmissionKind
    value: str = Field(min_length=1)


class AuthMethodSelection(BaseModel):
    """Auth method selection submitted through the shared chat input channel."""

    kind: Literal["auth_method"] = "auth_method"
    value: AuthMethod


class InteractionReplyRequest(BaseModel):
    """Request payload for interaction or auth reply submission."""

    mode: Literal["interaction", "auth"] = "interaction"
    interaction_id: Optional[int] = None
    response: Any = None
    auth_session_id: Optional[str] = None
    selection: Optional[AuthMethodSelection] = None
    submission: Optional[AuthSubmission] = None
    idempotency_key: Optional[str] = None

    @model_validator(mode="after")
    def validate_mode_specific_fields(self) -> "InteractionReplyRequest":
        if self.mode == "interaction":
            if self.interaction_id is None:
                raise ValueError("interaction_id is required when mode=interaction")
            return self
        if self.selection is not None and self.submission is not None:
            raise ValueError("selection and submission are mutually exclusive when mode=auth")
        if self.selection is None and self.submission is None:
            raise ValueError("selection or submission is required when mode=auth")
        if self.selection is not None:
            if self.auth_session_id is not None:
                raise ValueError("auth_session_id must be empty when selecting auth method")
            return self
        if not self.auth_session_id:
            raise ValueError("auth_session_id is required when submitting auth input")
        return self


class InteractionReplyResponse(BaseModel):
    """Response payload for interaction reply acceptance."""

    request_id: str
    status: RunStatus
    accepted: bool
    mode: Literal["interaction", "auth"] = "interaction"


class AuthSessionStatusResponse(BaseModel):
    """Backend-authored auth session truth for waiting_auth clients."""

    request_id: str
    waiting_auth: bool
    requested_execution_mode: Optional[ExecutionMode] = None
    effective_execution_mode: Optional[ExecutionMode] = None
    conversation_mode: Optional[ClientConversationMode] = None
    effective_interactive_require_user_reply: Optional[bool] = None
    effective_interactive_reply_timeout_sec: Optional[int] = None
    phase: Optional[AuthSessionPhase] = None
    timed_out: bool = False
    available_methods: List[AuthMethod] = Field(default_factory=list)
    selected_method: Optional[AuthMethod] = None
    auth_session_id: Optional[str] = None
    provider_id: Optional[str] = None
    transport: Optional[str] = None
    session_status: Optional[str] = None
    challenge_kind: Optional[AuthChallengeKind] = None
    timeout_sec: Optional[int] = Field(default=None, ge=1)
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    server_now: str
    last_error: Optional[str] = None
    source_attempt: Optional[int] = Field(default=None, ge=1)
    target_attempt: Optional[int] = Field(default=None, ge=1)
    resume_ticket_id: Optional[str] = None
    ticket_consumed: bool = False
    pending_owner: Optional[PendingOwner] = None
