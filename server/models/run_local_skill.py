"""Run-local skill snapshot models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class RunLocalSkillSource(str, Enum):
    INSTALLED = "installed"
    TEMP_UPLOAD = "temp_upload"
    RUN_SNAPSHOT = "run_snapshot"


class RunLocalSkillRef(BaseModel):
    skill_id: str
    engine: str
    snapshot_dir: Path
    source: RunLocalSkillSource
