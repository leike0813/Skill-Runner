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

# Run database path
_C.SYSTEM.RUNS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "runs.db")

# Run cleanup retention in days (0 disables cleanup)
_C.SYSTEM.RUN_RETENTION_DAYS = 7

# Run cleanup scheduler interval in hours
_C.SYSTEM.RUN_CLEANUP_INTERVAL_HOURS = 12

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
