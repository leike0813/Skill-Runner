"""
Core Configuration Definitions.

This module defines the default structure and values for the application's
configuration system using `yacs`. It serves as the single source of truth
for all configurable parameters.

Configuration is organized into sections:
- SYSTEM: Global paths and environment settings.
"""

import os
from pathlib import Path
from yacs.config import CfgNode as CN  # type: ignore[import-untyped]
import platform


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_container_runtime() -> bool:
    if os.path.exists("/.dockerenv"):
        return True
    cgroup = Path("/proc/1/cgroup")
    if cgroup.exists():
        try:
            lowered = cgroup.read_text(encoding="utf-8", errors="ignore").lower()
            return "docker" in lowered or "containerd" in lowered or "kubepods" in lowered
        except Exception:
            return False
    return False


def _default_local_base_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "SkillRunner"
        return Path.home() / "AppData" / "Local" / "SkillRunner"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "SkillRunner"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "skill-runner"
    return Path.home() / ".local" / "share" / "skill-runner"


_C = CN()

# -----------------------------------------------------------------------------
# System Configuration
# -----------------------------------------------------------------------------
_C.SYSTEM = CN()
# Root directory of the project (calculated dynamically if not set)
_C.SYSTEM.ROOT = str(Path(__file__).parent.parent)

# Data directory for storing runs, artifacts, etc.
# Check env SKILL_RUNNER_DATA_DIR first, then default to PROJECT_ROOT/data
_default_data_dir = "/data" if _is_container_runtime() else os.path.join(_C.SYSTEM.ROOT, "data")
_C.SYSTEM.DATA_DIR = os.environ.get("SKILL_RUNNER_DATA_DIR", _default_data_dir)

# Agent managed cache root (independent from data dir)
_default_agent_cache = (
    "/opt/cache/skill-runner" if _is_container_runtime() else str(_default_local_base_dir() / "agent-cache")
)
_C.SYSTEM.AGENT_CACHE_DIR = os.environ.get("SKILL_RUNNER_AGENT_CACHE_DIR", _default_agent_cache)

# Agent isolated home/config root
_C.SYSTEM.AGENT_HOME = os.environ.get(
    "SKILL_RUNNER_AGENT_HOME",
    os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "agent-home"),
)

# Managed npm prefix for engine CLIs
_C.SYSTEM.NPM_PREFIX = os.environ.get(
    "SKILL_RUNNER_NPM_PREFIX",
    os.environ.get("NPM_CONFIG_PREFIX", os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "npm")),
)

# Skills directory
_C.SYSTEM.SKILLS_DIR = os.path.join(_C.SYSTEM.ROOT, "skills")

# Runs directory (where execution happens)
_C.SYSTEM.RUNS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "runs")

# Requests directory (pre-run staging)
_C.SYSTEM.REQUESTS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "requests")

# uv cache directory (can be overridden via UV_CACHE_DIR)
_C.SYSTEM.UV_CACHE_DIR = os.environ.get("UV_CACHE_DIR", os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "uv_cache"))

# uv venv directory (can be overridden via UV_PROJECT_ENVIRONMENT)
_C.SYSTEM.UV_PROJECT_ENVIRONMENT = os.environ.get(
    "UV_PROJECT_ENVIRONMENT",
    os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "uv_venv")
)

# OpenCode model catalog refresh interval (minutes)
_C.SYSTEM.OPENCODE_MODELS_REFRESH_INTERVAL_MINUTES = int(
    os.environ.get("OPENCODE_MODELS_REFRESH_INTERVAL_MINUTES", "60")
)

# OpenCode model probe timeout (seconds)
_C.SYSTEM.OPENCODE_MODELS_PROBE_TIMEOUT_SEC = int(
    os.environ.get("OPENCODE_MODELS_PROBE_TIMEOUT_SEC", "20")
)

# OpenCode startup model probe toggle
_C.SYSTEM.OPENCODE_MODELS_STARTUP_PROBE = _env_bool(
    "OPENCODE_MODELS_STARTUP_PROBE",
    True,
)

# OpenCode model cache file path
_C.SYSTEM.OPENCODE_MODELS_CACHE_PATH = os.environ.get(
    "OPENCODE_MODELS_CACHE_PATH",
    os.path.join(_C.SYSTEM.DATA_DIR, "engine_catalog", "opencode_models_cache.json"),
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
_C.SYSTEM.SKILLS_INVALID_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".invalid")

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

# Hard timeout for engine subprocess execution (seconds)
_C.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS = int(
    os.environ.get("SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS", "1200")
)

# Experimental codex device-auth proxy
_C.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_ENABLED = _env_bool(
    "ENGINE_AUTH_DEVICE_PROXY_ENABLED",
    True,
)
_C.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS = int(
    os.environ.get("ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS", "900")
)
_C.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL = os.environ.get(
    "ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL",
    "",
)

# Interactive session timeout (seconds)
_C.SYSTEM.SESSION_TIMEOUT_SEC = int(
    os.environ.get("SKILL_RUNNER_SESSION_TIMEOUT_SEC", "1200")
)

def get_cfg_defaults():
    """
    Get a yacs CfgNode object with default values.
    Returns a clone to ensure thread-safety during initialization.
    """
    return _C.clone()
