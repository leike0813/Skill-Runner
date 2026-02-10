import sys
import os
from pathlib import Path
import pytest

# Add project root to sys.path
# This ensures that 'server' is importable as a top-level module during tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_config_dirs(tmp_path):
    from server.config import config

    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    old_skill_installs_db = config.SYSTEM.SKILL_INSTALLS_DB
    old_skill_installs_dir = config.SYSTEM.SKILL_INSTALLS_DIR
    old_skills_archive_dir = config.SYSTEM.SKILLS_ARCHIVE_DIR
    old_skills_staging_dir = config.SYSTEM.SKILLS_STAGING_DIR
    old_temp_skill_runs_db = config.SYSTEM.TEMP_SKILL_RUNS_DB
    old_temp_skill_requests_dir = config.SYSTEM.TEMP_SKILL_REQUESTS_DIR
    old_temp_skill_package_max_bytes = config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES
    old_temp_skill_cleanup_interval_hours = config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS
    old_temp_skill_orphan_retention_hours = config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS

    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.SYSTEM.SKILL_INSTALLS_DB = str(tmp_path / "skill_installs.db")
    config.SYSTEM.SKILL_INSTALLS_DIR = str(tmp_path / "skill_installs")
    config.SYSTEM.SKILLS_ARCHIVE_DIR = str(tmp_path / "skills" / ".archive")
    config.SYSTEM.SKILLS_STAGING_DIR = str(tmp_path / "skills" / ".staging")
    config.SYSTEM.TEMP_SKILL_RUNS_DB = str(tmp_path / "temp_skill_runs.db")
    config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = str(tmp_path / "temp_skill_runs" / "requests")
    config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = 20 * 1024 * 1024
    config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS = 12
    config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS = 24
    config.freeze()

    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.SYSTEM.SKILL_INSTALLS_DB = old_skill_installs_db
        config.SYSTEM.SKILL_INSTALLS_DIR = old_skill_installs_dir
        config.SYSTEM.SKILLS_ARCHIVE_DIR = old_skills_archive_dir
        config.SYSTEM.SKILLS_STAGING_DIR = old_skills_staging_dir
        config.SYSTEM.TEMP_SKILL_RUNS_DB = old_temp_skill_runs_db
        config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = old_temp_skill_requests_dir
        config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES = old_temp_skill_package_max_bytes
        config.SYSTEM.TEMP_SKILL_CLEANUP_INTERVAL_HOURS = old_temp_skill_cleanup_interval_hours
        config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS = old_temp_skill_orphan_retention_hours
        config.freeze()
