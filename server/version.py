"""Backend version helpers."""

from __future__ import annotations

from functools import lru_cache
from importlib import metadata
from pathlib import Path
import tomllib
from typing import Any


_PACKAGE_NAME = "skill-runner"


@lru_cache(maxsize=1)
def get_backend_version() -> str:
    """Return the Skill-Runner backend version from source or package metadata."""

    pyproject_version = _read_pyproject_version(_project_root() / "pyproject.toml")
    if pyproject_version:
        return pyproject_version
    try:
        version = metadata.version(_PACKAGE_NAME).strip()
    except metadata.PackageNotFoundError:
        version = ""
    if version:
        return version

    return "0.0.0"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_pyproject_version(path: Path) -> str:
    try:
        payload: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    project = payload.get("project")
    if not isinstance(project, dict):
        return ""
    value = project.get("version")
    return value.strip() if isinstance(value, str) else ""
