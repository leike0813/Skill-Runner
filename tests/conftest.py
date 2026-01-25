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

    config.defrost()
    config.SYSTEM.RUNS_DIR = str(tmp_path / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "requests")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.freeze()

    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.freeze()
