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
    SUCCEEDED = "succeeded" # Finished successfully (exit code 0)
    FAILED = "failed"       # Finished with error or non-zero exit code
    CANCELED = "canceled"   # Terminated by user or timeout


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
