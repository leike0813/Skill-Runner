from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_trust_strategy_invocation_paths_cover_run_and_auth() -> None:
    run_job_lifecycle_service = _read("server/services/orchestration/run_job_lifecycle_service.py")
    run_attempt_preparation_service = _read(
        "server/services/orchestration/run_attempt_preparation_service.py"
    )
    run_attempt_execution_service = _read(
        "server/services/orchestration/run_attempt_execution_service.py"
    )
    engine_auth_manager = _read("server/services/engine_management/engine_auth_flow_manager.py")
    ui_shell_manager = _read("server/services/ui/ui_shell_manager.py")
    harness_runtime = _read("agent_harness/runtime.py")
    run_cleanup_manager = _read("server/services/orchestration/run_cleanup_manager.py")

    # API/harness run execution both go through the canonical lifecycle service path.
    assert "orchestrator.run_attempt_execution_service.execute(" in run_job_lifecycle_service
    assert "run_folder_git_initializer.ensure_git_repo(run_dir)" in run_attempt_preparation_service
    assert "trust_manager_backend.register_run_folder(" in run_attempt_execution_service
    assert "trust_manager_backend.remove_run_folder(" in run_attempt_execution_service

    # CLI delegated auth start path runs through session starter trust injection.
    assert "run_folder_git_initializer.ensure_git_repo(session_dir)" in engine_auth_manager
    assert "self.trust_manager.register_run_folder(engine, session_dir)" in engine_auth_manager
    assert "self.trust_manager.remove_run_folder(session.trust_engine, session.trust_path)" in engine_auth_manager

    # UI shell and harness should share the same git-bootstrap-before-trust rule.
    assert "run_folder_git_initializer.ensure_git_repo(session_dir)" in ui_shell_manager
    assert "run_folder_git_initializer.ensure_git_repo(run_dir)" in harness_runtime
    assert '"claude"' in harness_runtime

    # stale cleanup path remains active.
    assert "run_folder_trust_manager.cleanup_stale_entries(" in run_cleanup_manager
