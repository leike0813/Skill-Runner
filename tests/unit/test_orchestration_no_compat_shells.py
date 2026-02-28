from pathlib import Path


def test_orchestration_compat_shells_removed() -> None:
    removed = [
        Path("server/services/orchestration/codex_config_manager.py"),
        Path("server/services/orchestration/config_generator.py"),
        Path("server/services/orchestration/opencode_model_catalog.py"),
    ]
    for target in removed:
        assert not target.exists(), f"Compatibility shell should be removed: {target}"
