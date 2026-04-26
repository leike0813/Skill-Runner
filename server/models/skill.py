"""Skill-domain models."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

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
    default_options: Dict[str, Any] = Field(default_factory=dict)


class SkillMcpDeclaration(BaseModel):
    """Declares governed MCP registry IDs required by a skill."""

    required_servers: List[str] = Field(default_factory=list)

    @field_validator("required_servers")
    @classmethod
    def _validate_required_servers(cls, value: List[str]) -> List[str]:
        normalized: List[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("mcp.required_servers must contain non-empty strings")
            stripped = item.strip()
            if stripped in normalized:
                raise ValueError("mcp.required_servers must contain unique strings")
            normalized.append(stripped)
        return normalized


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
    mcp: Optional[SkillMcpDeclaration] = None
    runtime: Optional[RuntimeDefinition] = None
