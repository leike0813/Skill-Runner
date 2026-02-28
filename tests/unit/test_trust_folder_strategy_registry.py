from pathlib import Path

from server.engines.common.trust_registry import create_default_trust_registry


def test_trust_registry_resolves_codex_and_gemini_strategies(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    registry = create_default_trust_registry(
        codex_config_path=tmp_path / ".codex" / "config.toml",
        gemini_trusted_path=tmp_path / ".gemini" / "trustedFolders.json",
        runs_root=runs_root,
    )

    codex_strategy = registry.resolve("codex")
    gemini_strategy = registry.resolve("gemini")
    noop_strategy = registry.resolve("iflow")

    assert codex_strategy.__class__.__name__ == "CodexTrustFolderStrategy"
    assert gemini_strategy.__class__.__name__ == "GeminiTrustFolderStrategy"
    assert noop_strategy.__class__.__name__ == "_NoopTrustFolderStrategy"


def test_trust_registry_noop_is_safe_for_unregistered_engine(tmp_path: Path) -> None:
    registry = create_default_trust_registry(
        codex_config_path=tmp_path / ".codex" / "config.toml",
        gemini_trusted_path=tmp_path / ".gemini" / "trustedFolders.json",
        runs_root=tmp_path / "runs",
    )
    strategy = registry.resolve("opencode")

    strategy.register("/tmp/non-existent")
    strategy.remove("/tmp/non-existent")
    strategy.bootstrap_parent_trust("/tmp/non-existent")
    strategy.cleanup_stale(set())
