"""Interactive turn protocol models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import AdapterTurnOutcome, RunStatus


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
