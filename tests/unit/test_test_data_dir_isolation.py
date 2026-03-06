from __future__ import annotations

from pathlib import Path

from server.config import config


def test_tests_use_isolated_data_dir() -> None:
    repo_data = (Path(__file__).resolve().parents[2] / "data").resolve()
    data_dir = Path(config.SYSTEM.DATA_DIR).resolve()
    runs_db = Path(config.SYSTEM.RUNS_DB).resolve()

    assert data_dir != repo_data
    assert repo_data not in data_dir.parents
    assert repo_data not in runs_db.parents
