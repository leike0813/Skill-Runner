from __future__ import annotations

from pathlib import Path

from agent_harness.config import HARNESS_RUN_ROOT_ENV, resolve_harness_config
from server.services.orchestration.runtime_profile import reset_runtime_profile_cache


def test_config_defaults_run_root_under_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SKILL_RUNNER_RUNTIME_MODE", "local")
    monkeypatch.setenv("SKILL_RUNNER_DATA_DIR", str(tmp_path / "data-dir"))
    monkeypatch.delenv(HARNESS_RUN_ROOT_ENV, raising=False)
    reset_runtime_profile_cache()

    config = resolve_harness_config()
    assert config.run_root == (tmp_path / "data-dir" / "harness_runs").resolve()
    assert config.run_root.exists()


def test_config_harness_run_root_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SKILL_RUNNER_RUNTIME_MODE", "local")
    monkeypatch.setenv("SKILL_RUNNER_DATA_DIR", str(tmp_path / "data-dir"))
    monkeypatch.setenv(HARNESS_RUN_ROOT_ENV, str(tmp_path / "custom-runs"))
    reset_runtime_profile_cache()

    config = resolve_harness_config()
    assert config.run_root == (tmp_path / "custom-runs").resolve()
    assert config.run_root.exists()
