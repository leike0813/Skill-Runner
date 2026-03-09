"""
Core configuration definitions and runtime config singleton.

This module is the single source of truth for yacs configuration defaults,
and also exposes the frozen `config` object used by runtime code.
"""

import os
import platform
import logging
from pathlib import Path

from yacs.config import CfgNode as CN  # type: ignore[import-untyped]


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
        except OSError:
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
_C.SYSTEM.ROOT = str(Path(__file__).parent.parent)

_default_data_dir = "/data" if _is_container_runtime() else os.path.join(_C.SYSTEM.ROOT, "data")
_C.SYSTEM.DATA_DIR = os.environ.get("SKILL_RUNNER_DATA_DIR", _default_data_dir)

_C.SYSTEM.LOGGING = CN()
_C.SYSTEM.LOGGING.LEVEL = "INFO"
_C.SYSTEM.LOGGING.DIR = os.environ.get("LOG_DIR", os.path.join(_C.SYSTEM.DATA_DIR, "logs"))
_C.SYSTEM.LOGGING.FILE_BASENAME = os.environ.get("LOG_FILE_BASENAME", "skill_runner.log")
_C.SYSTEM.LOGGING.FORMAT = "text"
_C.SYSTEM.LOGGING.ROTATION_WHEN = os.environ.get("LOG_ROTATION_WHEN", "midnight")
_C.SYSTEM.LOGGING.ROTATION_INTERVAL = int(os.environ.get("LOG_ROTATION_INTERVAL", "1"))
_C.SYSTEM.LOGGING.RETENTION_DAYS = 7
_C.SYSTEM.LOGGING.DIR_MAX_BYTES = 512 * 1024 * 1024
_C.SYSTEM.RUN_AUDIT_SERVICE_LOG_MAX_BYTES = 8 * 1024 * 1024
_C.SYSTEM.RUN_AUDIT_SERVICE_LOG_BACKUP_COUNT = 3
_C.SYSTEM.PROCESS_SUPERVISOR_ENABLED = _env_bool("PROCESS_SUPERVISOR_ENABLED", True)
_C.SYSTEM.PROCESS_SWEEP_INTERVAL_SEC = int(os.environ.get("PROCESS_SWEEP_INTERVAL_SEC", "15"))
_C.SYSTEM.PROCESS_TERMINATE_GRACE_SEC = int(os.environ.get("PROCESS_TERMINATE_GRACE_SEC", "3"))
_C.SYSTEM.PROCESS_KILL_GRACE_SEC = int(os.environ.get("PROCESS_KILL_GRACE_SEC", "3"))

_C.SYSTEM.SETTINGS_FILE = os.path.join(_C.SYSTEM.DATA_DIR, "system_settings.json")
_C.SYSTEM.SETTINGS_BOOTSTRAP_FILE = os.path.join(
    _C.SYSTEM.ROOT,
    "server",
    "config",
    "policy",
    "system_settings.bootstrap.json",
)

_default_agent_cache = (
    "/opt/cache/skill-runner" if _is_container_runtime() else str(_default_local_base_dir() / "agent-cache")
)
_C.SYSTEM.AGENT_CACHE_DIR = os.environ.get("SKILL_RUNNER_AGENT_CACHE_DIR", _default_agent_cache)
_C.SYSTEM.AGENT_HOME = os.environ.get(
    "SKILL_RUNNER_AGENT_HOME",
    os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "agent-home"),
)
_C.SYSTEM.NPM_PREFIX = os.environ.get(
    "SKILL_RUNNER_NPM_PREFIX",
    os.environ.get("NPM_CONFIG_PREFIX", os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "npm")),
)

_C.SYSTEM.SKILLS_DIR = os.path.join(_C.SYSTEM.ROOT, "skills")
_C.SYSTEM.RUNS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "runs")
_C.SYSTEM.REQUESTS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "requests")
_C.SYSTEM.TMP_UPLOADS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "tmp_uploads")

_C.SYSTEM.UV_CACHE_DIR = os.environ.get("UV_CACHE_DIR", os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "uv_cache"))
_C.SYSTEM.UV_PROJECT_ENVIRONMENT = os.environ.get(
    "UV_PROJECT_ENVIRONMENT",
    os.path.join(_C.SYSTEM.AGENT_CACHE_DIR, "uv_venv")
)

_C.SYSTEM.ENGINE_MODELS_CATALOG_REFRESH_INTERVAL_MINUTES = int(
    os.environ.get(
        "ENGINE_MODELS_CATALOG_REFRESH_INTERVAL_MINUTES",
        os.environ.get("OPENCODE_MODELS_REFRESH_INTERVAL_MINUTES", "60"),
    )
)
_C.SYSTEM.ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC = int(
    os.environ.get(
        "ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC",
        os.environ.get("OPENCODE_MODELS_PROBE_TIMEOUT_SEC", "20"),
    )
)
_C.SYSTEM.ENGINE_MODELS_CATALOG_STARTUP_PROBE = _env_bool(
    "ENGINE_MODELS_CATALOG_STARTUP_PROBE",
    _env_bool("OPENCODE_MODELS_STARTUP_PROBE", True),
)
_C.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR = os.environ.get(
    "ENGINE_MODELS_CATALOG_CACHE_DIR",
    os.path.join(_C.SYSTEM.DATA_DIR, "engine_catalog"),
)
_C.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE = os.environ.get(
    "ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE",
    "{engine}_models_cache.json",
)

# Legacy compatibility aliases (phase-1): kept for callers/tests migrating from opencode-only keys.
_C.SYSTEM.OPENCODE_MODELS_REFRESH_INTERVAL_MINUTES = int(
    _C.SYSTEM.ENGINE_MODELS_CATALOG_REFRESH_INTERVAL_MINUTES
)
_C.SYSTEM.OPENCODE_MODELS_PROBE_TIMEOUT_SEC = int(
    _C.SYSTEM.ENGINE_MODELS_CATALOG_PROBE_TIMEOUT_SEC
)
_C.SYSTEM.OPENCODE_MODELS_STARTUP_PROBE = bool(
    _C.SYSTEM.ENGINE_MODELS_CATALOG_STARTUP_PROBE
)
_C.SYSTEM.OPENCODE_MODELS_CACHE_PATH = os.environ.get(
    "OPENCODE_MODELS_CACHE_PATH",
    os.path.join(
        _C.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR,
        _C.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE.format(engine="opencode"),
    ),
)

_C.SYSTEM.RUNS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "runs.db")
_C.SYSTEM.SKILL_INSTALLS_DB = os.path.join(_C.SYSTEM.DATA_DIR, "skill_installs.db")

_C.SYSTEM.SKILL_INSTALLS_DIR = os.path.join(_C.SYSTEM.DATA_DIR, "skill_installs")
_C.SYSTEM.SKILLS_ARCHIVE_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".archive")
_C.SYSTEM.SKILLS_STAGING_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".staging")
_C.SYSTEM.SKILLS_INVALID_DIR = os.path.join(_C.SYSTEM.SKILLS_DIR, ".invalid")

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

_C.SYSTEM.RUN_RETENTION_DAYS = 7
_C.SYSTEM.RUN_CLEANUP_INTERVAL_HOURS = 12

_C.SYSTEM.CONCURRENCY = CN()
_C.SYSTEM.CONCURRENCY.MAX_CONCURRENT_HARD_CAP = 16
_C.SYSTEM.CONCURRENCY.MAX_QUEUE_SIZE = 128
_C.SYSTEM.CONCURRENCY.CPU_FACTOR = 0.75
_C.SYSTEM.CONCURRENCY.MEM_RESERVE_MB = 1024
_C.SYSTEM.CONCURRENCY.ESTIMATED_MEM_PER_RUN_MB = 1024
_C.SYSTEM.CONCURRENCY.FD_RESERVE = 256
_C.SYSTEM.CONCURRENCY.ESTIMATED_FD_PER_RUN = 64
_C.SYSTEM.CONCURRENCY.PID_RESERVE = 128
_C.SYSTEM.CONCURRENCY.ESTIMATED_PID_PER_RUN = 1
_C.SYSTEM.CONCURRENCY.FALLBACK_MAX_CONCURRENT = 2

_C.SYSTEM.UI_BASIC_AUTH_ENABLED = _env_bool("UI_BASIC_AUTH_ENABLED", False)
_C.SYSTEM.UI_BASIC_AUTH_USERNAME = os.environ.get("UI_BASIC_AUTH_USERNAME", "")
_C.SYSTEM.UI_BASIC_AUTH_PASSWORD = os.environ.get("UI_BASIC_AUTH_PASSWORD", "")

_C.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS = int(
    os.environ.get("SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS", "1200")
)
_C.SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS = float(
    os.environ.get("SKILL_RUNNER_AUTH_DETECTION_IDLE_GRACE_SECONDS", "3")
)
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
_C.SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED = _env_bool(
    "ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED",
    False,
)
_C.SYSTEM.SESSION_TIMEOUT_SEC = int(
    os.environ.get("SKILL_RUNNER_SESSION_TIMEOUT_SEC", "1200")
)


def get_cfg_defaults():
    """Return a clone of default config for safe initialization."""
    return _C.clone()


config = get_cfg_defaults()
config.freeze()

logger = logging.getLogger(__name__)
