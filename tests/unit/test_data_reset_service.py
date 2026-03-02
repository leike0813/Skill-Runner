from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from scripts import reset_project_data
from server.services.platform.data_reset_service import DataResetOptions, DataResetService


def _build_fake_config(tmp_path: Path) -> SimpleNamespace:
    data_dir = tmp_path / "data"
    return SimpleNamespace(
        SYSTEM=SimpleNamespace(
            DATA_DIR=str(data_dir),
            RUNS_DB=str(data_dir / "runs.db"),
            SKILL_INSTALLS_DB=str(data_dir / "skill_installs.db"),
            TEMP_SKILL_RUNS_DB=str(data_dir / "temp_skill_runs.db"),
            ENGINE_UPGRADES_DB=str(data_dir / "engine_upgrades.db"),
            RUNS_DIR=str(data_dir / "runs"),
            REQUESTS_DIR=str(data_dir / "requests"),
            TEMP_SKILL_REQUESTS_DIR=str(data_dir / "temp_skill_runs" / "requests"),
            SKILL_INSTALLS_DIR=str(data_dir / "skill_installs"),
            OPENCODE_MODELS_CACHE_PATH=str(data_dir / "engine_catalog" / "opencode_models_cache.json"),
            SETTINGS_FILE=str(data_dir / "system_settings.json"),
            ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=True,
            LOGGING=SimpleNamespace(DIR=str(data_dir / "logs")),
        )
    )


def test_data_reset_service_build_targets_includes_expected_optional_paths(tmp_path: Path):
    service = DataResetService(cfg=_build_fake_config(tmp_path))
    options = DataResetOptions(
        include_logs=True,
        include_engine_catalog=True,
        include_agent_status=True,
        include_engine_auth_sessions=True,
    )
    targets = service.build_targets(options)
    data_dir = (tmp_path / "data").resolve()

    assert (data_dir / "ui_shell_sessions") in targets.optional_paths
    assert (data_dir / "system_settings.json") in targets.optional_paths
    assert (data_dir / "agent_status.json") in targets.optional_paths
    assert (data_dir / "engine_auth_sessions") in targets.optional_paths
    assert (data_dir / "logs") in targets.optional_paths
    assert (data_dir / "engine_catalog" / "opencode_models_cache.json") in targets.optional_paths


def test_data_reset_service_hides_engine_auth_targets_when_feature_disabled(tmp_path: Path):
    cfg = _build_fake_config(tmp_path)
    cfg.SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED = False
    service = DataResetService(cfg=cfg)
    targets = service.build_targets(DataResetOptions(include_engine_auth_sessions=True))

    assert (tmp_path / "data" / "engine_auth_sessions").resolve() not in targets.optional_paths


def test_data_reset_service_execute_reset_deletes_targets_and_recreates_dirs(tmp_path: Path):
    service = DataResetService(cfg=_build_fake_config(tmp_path))
    options = DataResetOptions(
        include_logs=True,
        include_engine_catalog=True,
        include_agent_status=True,
        include_engine_auth_sessions=True,
    )
    targets = service.build_targets(options)

    for file_path in targets.db_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("db", encoding="utf-8")
    for dir_path in targets.data_dirs:
        (dir_path / "nested").mkdir(parents=True, exist_ok=True)
        (dir_path / "nested" / "x.txt").write_text("x", encoding="utf-8")
    for optional_path in targets.optional_paths:
        if optional_path.suffix:
            optional_path.parent.mkdir(parents=True, exist_ok=True)
            optional_path.write_text("x", encoding="utf-8")
        else:
            optional_path.mkdir(parents=True, exist_ok=True)
            (optional_path / "x.log").write_text("x", encoding="utf-8")

    result = service.execute_reset(options)

    assert result.dry_run is False
    assert result.deleted_count == len(targets.all_paths())
    assert result.missing_count == 0
    assert result.recreated_count == len(targets.recreate_dirs)
    for recreate_path in targets.recreate_dirs:
        assert recreate_path.exists()


def test_reset_script_delegates_to_shared_data_reset_service(monkeypatch):
    calls: dict[str, object] = {}
    fake_targets = SimpleNamespace(
        data_dir=Path("/tmp/skill-runner"),
        db_files=(),
        data_dirs=(),
        optional_paths=(),
        recreate_dirs=(),
        all_paths=lambda: (),
    )

    def _build_targets(options):  # noqa: ANN001
        calls["build"] = options
        return fake_targets

    def _execute_reset(options):  # noqa: ANN001
        calls["execute"] = options
        return SimpleNamespace(
            path_results=(),
            deleted_count=0,
            missing_count=0,
            recreated_count=0,
        )

    monkeypatch.setattr(
        reset_project_data,
        "data_reset_service",
        SimpleNamespace(build_targets=_build_targets, execute_reset=_execute_reset),
    )
    monkeypatch.setattr(
        reset_project_data,
        "_print_targets",
        lambda _targets, dry_run: None,  # noqa: ARG005
    )
    monkeypatch.setattr(reset_project_data, "_confirm_or_exit", lambda _yes: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset_project_data.py",
            "--yes",
            "--include-logs",
            "--include-engine-catalog",
            "--include-agent-status",
            "--include-engine-auth-sessions",
        ],
    )

    exit_code = reset_project_data.main()
    assert exit_code == 0
    assert calls["build"] == calls["execute"]
    options = calls["execute"]
    assert getattr(options, "include_logs") is True
    assert getattr(options, "include_engine_catalog") is True
    assert getattr(options, "include_agent_status") is True
    assert getattr(options, "include_engine_auth_sessions") is True
    assert getattr(options, "dry_run") is False
