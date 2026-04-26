import sys
from pathlib import Path
import pytest

# Add project root to sys.path
# This ensures that 'server' is importable as a top-level module during tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from server.services.orchestration.runtime_observability_ports import install_runtime_observability_ports
from server.services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports


@pytest.fixture(autouse=True)
def _install_runtime_ports():
    install_runtime_protocol_ports()
    install_runtime_observability_ports()
    yield


@pytest.fixture(autouse=True)
def _isolate_persistence_root(tmp_path):
    from server.config import config

    old_data_dir = config.SYSTEM.DATA_DIR
    old_logging_dir = config.SYSTEM.LOGGING.DIR
    old_settings_file = config.SYSTEM.SETTINGS_FILE
    old_mcp_registry_file = config.SYSTEM.MCP_REGISTRY_FILE
    old_mcp_secrets_file = config.SYSTEM.MCP_SECRETS_FILE
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    old_tmp_uploads_dir = config.SYSTEM.TMP_UPLOADS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    old_skill_installs_db = config.SYSTEM.SKILL_INSTALLS_DB
    old_skill_installs_dir = config.SYSTEM.SKILL_INSTALLS_DIR
    old_skills_archive_dir = config.SYSTEM.SKILLS_ARCHIVE_DIR
    old_skills_staging_dir = config.SYSTEM.SKILLS_STAGING_DIR
    old_skills_invalid_dir = config.SYSTEM.SKILLS_INVALID_DIR
    old_agent_cache_dir = config.SYSTEM.AGENT_CACHE_DIR
    old_agent_home = config.SYSTEM.AGENT_HOME
    old_npm_prefix = config.SYSTEM.NPM_PREFIX
    old_uv_cache_dir = config.SYSTEM.UV_CACHE_DIR
    old_uv_project_environment = config.SYSTEM.UV_PROJECT_ENVIRONMENT
    old_engine_catalog_cache_dir = config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR
    old_opencode_models_cache_path = config.SYSTEM.OPENCODE_MODELS_CACHE_PATH
    old_temp_skill_package_max_bytes = config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES
    old_temp_skill_cleanup_interval_hours = config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS
    old_temp_skill_orphan_retention_hours = config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS
    old_temp_skill_runs_db = config.SYSTEM.TEMP_SKILL_RUNS_DB
    old_temp_skill_requests_dir = config.SYSTEM.TEMP_SKILL_REQUESTS_DIR

    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    config.defrost()
    config.SYSTEM.DATA_DIR = str(test_data_dir)
    config.SYSTEM.LOGGING.DIR = str(test_data_dir / "logs")
    config.SYSTEM.SETTINGS_FILE = str(test_data_dir / "system_settings.json")
    config.SYSTEM.MCP_REGISTRY_FILE = str(test_data_dir / "mcp_registry.json")
    config.SYSTEM.MCP_SECRETS_FILE = str(test_data_dir / "mcp_secrets.json")
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.SYSTEM.TMP_UPLOADS_DIR = str(test_data_dir / "tmp_uploads")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.SYSTEM.SKILL_INSTALLS_DB = str(tmp_path / "runs.db")
    config.SYSTEM.SKILL_INSTALLS_DIR = str(tmp_path / "skill_installs")
    config.SYSTEM.SKILLS_ARCHIVE_DIR = str(tmp_path / "skills" / ".archive")
    config.SYSTEM.SKILLS_STAGING_DIR = str(tmp_path / "skills" / ".staging")
    config.SYSTEM.SKILLS_INVALID_DIR = str(tmp_path / "skills" / ".invalid")
    config.SYSTEM.AGENT_CACHE_DIR = str(tmp_path / "agent-cache")
    config.SYSTEM.AGENT_HOME = str(tmp_path / "agent-cache" / "agent-home")
    config.SYSTEM.NPM_PREFIX = str(tmp_path / "agent-cache" / "npm")
    config.SYSTEM.UV_CACHE_DIR = str(tmp_path / "agent-cache" / "uv_cache")
    config.SYSTEM.UV_PROJECT_ENVIRONMENT = str(tmp_path / "agent-cache" / "uv_venv")
    config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR = str(tmp_path / "engine_catalog")
    config.SYSTEM.OPENCODE_MODELS_CACHE_PATH = str(tmp_path / "engine_catalog" / "opencode_models_cache.json")
    config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = 20 * 1024 * 1024
    config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS = 12
    config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS = 24
    config.SYSTEM.TEMP_SKILL_RUNS_DB = str(tmp_path / "temp_skill_runs.db")
    config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = str(tmp_path / "temp_skill_runs" / "requests")
    config.freeze()

    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.DATA_DIR = old_data_dir
        config.SYSTEM.LOGGING.DIR = old_logging_dir
        config.SYSTEM.SETTINGS_FILE = old_settings_file
        config.SYSTEM.MCP_REGISTRY_FILE = old_mcp_registry_file
        config.SYSTEM.MCP_SECRETS_FILE = old_mcp_secrets_file
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.SYSTEM.TMP_UPLOADS_DIR = old_tmp_uploads_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.SYSTEM.SKILL_INSTALLS_DB = old_skill_installs_db
        config.SYSTEM.SKILL_INSTALLS_DIR = old_skill_installs_dir
        config.SYSTEM.SKILLS_ARCHIVE_DIR = old_skills_archive_dir
        config.SYSTEM.SKILLS_STAGING_DIR = old_skills_staging_dir
        config.SYSTEM.SKILLS_INVALID_DIR = old_skills_invalid_dir
        config.SYSTEM.AGENT_CACHE_DIR = old_agent_cache_dir
        config.SYSTEM.AGENT_HOME = old_agent_home
        config.SYSTEM.NPM_PREFIX = old_npm_prefix
        config.SYSTEM.UV_CACHE_DIR = old_uv_cache_dir
        config.SYSTEM.UV_PROJECT_ENVIRONMENT = old_uv_project_environment
        config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR = old_engine_catalog_cache_dir
        config.SYSTEM.OPENCODE_MODELS_CACHE_PATH = old_opencode_models_cache_path
        config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = old_temp_skill_package_max_bytes
        config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS = old_temp_skill_cleanup_interval_hours
        config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS = old_temp_skill_orphan_retention_hours
        config.SYSTEM.TEMP_SKILL_RUNS_DB = old_temp_skill_runs_db
        config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = old_temp_skill_requests_dir
        config.freeze()


@pytest.fixture
def temp_config_dirs(tmp_path):
    # Backward-compatible alias used by existing tests.
    yield tmp_path
