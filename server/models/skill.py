"""Skill-domain models."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import ExecutionMode


class ManifestArtifact(BaseModel):
    """Defines an expected output artifact from a skill execution."""

    role: str
    pattern: str
    mime: Optional[str] = None
    required: bool = False


class RuntimeDefinition(BaseModel):
    """Defines the runtime environment requirements for a skill."""

    language: str = "python"
    version: str = "3.11"
    dependencies: List[str] = []


class SkillManifest(BaseModel):
    """Represents metadata and configuration of a registered Skill."""

    id: str
    path: Optional[Path] = None
    version: str = "1.0.0"
    name: Optional[str] = None
    description: Optional[str] = None
    engines: List[str] = Field(default_factory=list)
    unsupported_engines: List[str] = Field(default_factory=list)
    effective_engines: List[str] = Field(default_factory=list)
    execution_modes: List[ExecutionMode] = Field(default_factory=lambda: [ExecutionMode.AUTO])
    max_attempt: Optional[int] = Field(default=None, ge=1)
    entrypoint: Optional[Dict[str, Any]] = {}
    artifacts: List[ManifestArtifact] = []
    schemas: Optional[Dict[str, str]] = {}
    engine_configs: Optional[Dict[str, str]] = {}
    runtime: Optional[RuntimeDefinition] = None
