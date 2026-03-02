from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_trust_strategy_invocation_paths_cover_run_and_auth() -> None:
    run_job_lifecycle_service = _read("server/services/orchestration/run_job_lifecycle_service.py")
    engine_auth_manager = _read("server/services/engine_management/engine_auth_flow_manager.py")
    run_cleanup_manager = _read("server/services/orchestration/run_cleanup_manager.py")

    # API/harness run execution both go through the canonical lifecycle service path.
    assert "run_folder_trust_manager.register_run_folder(" in run_job_lifecycle_service
    assert "run_folder_trust_manager.remove_run_folder(" in run_job_lifecycle_service

    # CLI delegated auth start path runs through session starter trust injection.
    assert "self.trust_manager.register_run_folder(engine, session_dir)" in engine_auth_manager
    assert "self.trust_manager.remove_run_folder(session.trust_engine, session.trust_path)" in engine_auth_manager

    # stale cleanup path remains active.
    assert "run_folder_trust_manager.cleanup_stale_entries(" in run_cleanup_manager
