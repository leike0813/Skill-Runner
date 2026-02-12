"""
Core Configuration Definitions.

This module defines the default structure and values for the application's
configuration system using `yacs`. It serves as the single source of truth
for all configurable parameters.

Configuration is organized into sections:
- SYSTEM: Global paths and environment settings.
- GEMINI: Gemini-specific adapter settings.
- CODEX: Codex-specific adapter settings.
"""

import os
from pathlib import Path
from yacs.config import CfgNode as CN  # type: ignore[import-untyped]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_C = CN()

# -----------------------------------------------------------------------------
# System Configuration
# -----------------------------------------------------------------------------
_C.SYSTEM = CN()
# Root directory of the project (calculated dynamically if not set)
_C.SYSTEM.ROOT = str(Path(__file__).parent.parent)

# Data directory for storing runs, artifacts, etc.
# Check env SKILL_RUNNER_DATA_DIR first, then default to PROJECT_ROOT/data
_C.SYSTEM.DATA_DIR = os.environ.get("SKILL_RUNNER_DATA_DIR", os.path.join(_C.SYSTEM.ROOT, "data"))

# Skills directory
_C.SYSTEM.SKILLS_DIR = os.path.join(_C.SYSTEM.ROOT, "skills")

# Runs directory (where execution happens)
_C.SYSTEM.RUNS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "runs")

# Requests directory (pre-run staging)
_C.SYSTEM.REQUESTS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "requests")

# uv cache directory (can be overridden via UV_CACHE_DIR)
_C.SYSTEM.UV_CACHE_DIR = os.environ.get("UV_CACHE_DIR", os.path.join(_C.SYSTEM.DATA_DIR, "uv_cache"))

# uv venv directory (can be overridden via UV_PROJECT_ENVIRONMENT)
_C.SYSTEM.UV_PROJECT_ENVIRONMENT = os.environ.get(
    "UV_PROJECT_ENVIRONMENT",
    os.path.join(_C.SYSTEM.DATA_DIR, "uv_venv")
)

# Run database path
_C.SYSTEM.RUNS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "runs.db")

# Skill package install status database path
_C.SYSTEM.SKILL_INSTALLS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "skill_installs.db")

# Engine upgrade task database path
_C.SYSTEM.ENGINE_UPGRADES_DB = os.path.join(_C.SYSTEM.DATA_DIR, "engine_upgrades.db")

# Skill package working directories
_C.SYSTEM.SKILL_INSTALLS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "skill_installs")
_C.SYSTEM.SKILLS_ARCHIVE_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".archive")
_C.SYSTEM.SKILLS_STAGING_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".staging")

# Temporary skill run working area
_C.SYSTEM.TEMP_SKILL_RUNS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "temp_skill_runs.db")
_C.SYSTEM.TEMP_SKILL_REQUESTS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "temp_skill_runs", "requests")
_C.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = int(
    os.environ.get("TEMP_SKILL_PACKAGE_MAX_BYTES", str(20 * 1024 * 1024))
)
_C.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS = int(
    os.environ.get("TEMP_SKILL_CLEANUP_INTERVAL_HOURS", "12")
)
_C.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS = int(
    os.environ.get("TEMP_SKILL_ORPHAN_RETENTION_HOURS", "24")
)

# Run cleanup retention in days (0 disables cleanup)
_C.SYSTEM.RUN_RETENTION_DAYS = 7

# Run cleanup scheduler interval in hours
_C.SYSTEM.RUN_CLEANUP_INTERVAL_HOURS = 12

# Concurrency policy config path
_C.SYSTEM.CONCURRENCY_POLICY = os.path.join(
    _C.SYSTEM.ROOT, "server", "assets", "configs", "concurrency_policy.json"
)

# UI basic auth
_C.SYSTEM.UI_BASIC_AUTH_ENABLED = _env_bool("UI_BASIC_AUTH_ENABLED", False)
_C.SYSTEM.UI_BASIC_AUTH_USERNAME = os.environ.get("UI_BASIC_AUTH_USERNAME", "")
_C.SYSTEM.UI_BASIC_AUTH_PASSWORD = os.environ.get("UI_BASIC_AUTH_PASSWORD", "")

# -----------------------------------------------------------------------------
# Gemini Configuration
# -----------------------------------------------------------------------------
_C.GEMINI = CN()
# Path to the default Jinja2 prompt template for Gemini
_C.GEMINI.DEFAULT_PROMPT_TEMPLATE = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "templates", "gemini_default.j2")

# -----------------------------------------------------------------------------
# Codex Configuration
# -----------------------------------------------------------------------------
_C.CODEX = CN()
# Enforced configuration file path
_C.CODEX.ENFORCED_CONFIG = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "configs", "codex_enforced.toml")
# Profile schema file path
_C.CODEX.PROFILE_SCHEMA = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "schemas", "codex_profile_schema.json")

# -----------------------------------------------------------------------------
# iFlow Configuration
# -----------------------------------------------------------------------------
_C.IFLOW = CN()
_C.IFLOW.DEFAULT_PROMPT_TEMPLATE = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "templates", "iflow_default.j2")
_C.IFLOW.ENFORCED_CONFIG = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "configs", "iflow_enforced.json")
_C.IFLOW.SETTINGS_SCHEMA = os.path.join(_C.SYSTEM.ROOT, "server", "assets", "schemas", "iflow_settings_schema.json")


def get_cfg_defaults():
    """
    Get a yacs CfgNode object with default values.
    Returns a clone to ensure thread-safety during initialization.
    """
    return _C.clone()
