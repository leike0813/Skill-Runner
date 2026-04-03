"""Engine-management domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EngineInfo(BaseModel):
    """Basic engine info returned by the engine registry."""

    engine: str
    cli_version_detected: Optional[str] = None


class EnginesResponse(BaseModel):
    """Response payload listing available engines."""

    engines: List[EngineInfo]


class EngineModelInfo(BaseModel):
    """Model entry returned by the engine registry."""

    id: str
    display_name: Optional[str] = None
    deprecated: bool = False
    notes: Optional[str] = None
    supported_effort: Optional[List[str]] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class EngineModelsResponse(BaseModel):
    """Response payload listing models for a specific engine."""

    engine: str
    cli_version_detected: Optional[str] = None
    snapshot_version_used: Optional[str] = None
    source: str
    fallback_reason: Optional[str] = None
    models: List[EngineModelInfo]


class EngineAuthStatusResponse(BaseModel):
    """Response payload for engine authentication observability."""

    engines: Dict[str, Dict[str, Any]]


class EngineAuthSessionStartRequest(BaseModel):
    """Request payload for starting engine auth session."""

    engine: str
    method: str = "auth"
    auth_method: Optional[str] = None
    provider_id: Optional[str] = None
    transport: Optional[str] = None


class EngineAuthSessionSnapshot(BaseModel):
    """Snapshot payload for engine auth session."""

    session_id: str
    engine: str
    method: str
    auth_method: Optional[str] = None
    transport: str = "oauth_proxy"
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    status: str
    input_kind: Optional[str] = None
    auth_url: Optional[str] = None
    user_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_mode: Optional[str] = None
    manual_fallback_used: bool = False
    oauth_callback_received: bool = False
    oauth_callback_at: Optional[str] = None
    transport_state_machine: Optional[str] = None
    orchestrator: Optional[str] = None
    log_root: Optional[str] = None
    deprecated: bool = False
    audit: Optional[Dict[str, Any]] = None
    terminal: bool = False


class EngineAuthSessionCancelResponse(BaseModel):
    """Response payload for canceling engine auth session."""

    session: EngineAuthSessionSnapshot
    canceled: bool


class EngineAuthSessionInputRequest(BaseModel):
    """Request payload for auth session user input."""

    kind: str
    value: str


class EngineAuthSessionInputResponse(BaseModel):
    """Response payload for auth session user input."""

    session: EngineAuthSessionSnapshot
    accepted: bool


class AuthSessionStartRequestV2(BaseModel):
    """V2 transport-grouped auth start request."""

    engine: str
    transport: str
    auth_method: str
    provider_id: Optional[str] = None


class AuthSessionSnapshotV2(BaseModel):
    """V2 transport-grouped auth session snapshot."""

    session_id: str
    engine: str
    transport: str
    auth_method: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    status: str
    input_kind: Optional[str] = None
    auth_url: Optional[str] = None
    user_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_mode: Optional[str] = None
    manual_fallback_used: bool = False
    oauth_callback_received: bool = False
    oauth_callback_at: Optional[str] = None
    transport_state_machine: Optional[str] = None
    orchestrator: Optional[str] = None
    log_root: Optional[str] = None
    audit: Optional[Dict[str, Any]] = None
    terminal: bool = False


class AuthSessionInputRequestV2(BaseModel):
    """V2 transport-grouped auth user input request."""

    kind: str
    value: str


class AuthSessionInputResponseV2(BaseModel):
    """V2 transport-grouped auth user input response."""

    session: AuthSessionSnapshotV2
    accepted: bool


class AuthSessionCancelResponseV2(BaseModel):
    """V2 transport-grouped auth cancel response."""

    session: AuthSessionSnapshotV2
    canceled: bool


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
    action: Optional[str] = None
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
    provider: Optional[str] = None
    model: Optional[str] = None


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
