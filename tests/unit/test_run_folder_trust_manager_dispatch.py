from pathlib import Path

from server.services.orchestration.run_folder_trust_manager import RunFolderTrustManager


def test_run_folder_trust_manager_has_no_engine_branches() -> None:
    target = Path("server/services/orchestration/run_folder_trust_manager.py")
    source = target.read_text(encoding="utf-8")
    assert 'if engine == "codex"' not in source
    assert 'if engine == "gemini"' not in source
    assert "self._registry.resolve(engine)" in source


def test_run_folder_trust_manager_dispatches_to_registry(monkeypatch, tmp_path: Path) -> None:
    manager = RunFolderTrustManager(
        codex_config_path=tmp_path / ".codex" / "config.toml",
        gemini_trusted_path=tmp_path / ".gemini" / "trustedFolders.json",
        runs_root=tmp_path / "runs",
    )

    calls: list[tuple[str, str]] = []

    class _FakeStrategy:
        def register(self, normalized_path: str) -> None:
            calls.append(("register", normalized_path))

        def remove(self, normalized_path: str) -> None:
            calls.append(("remove", normalized_path))

        def bootstrap_parent_trust(self, normalized_parent_path: str) -> None:
            calls.append(("bootstrap", normalized_parent_path))

        def cleanup_stale(self, active_normalized_paths: set[str]) -> None:
            calls.append(("cleanup", ",".join(sorted(active_normalized_paths))))

    class _FakeRegistry:
        def resolve(self, _engine: str):
            return _FakeStrategy()

        def iter_registered(self):
            return [("codex", _FakeStrategy()), ("gemini", _FakeStrategy())]

    monkeypatch.setattr(manager, "_registry", _FakeRegistry())
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)

    manager.register_run_folder("codex", run_dir)
    manager.remove_run_folder("codex", run_dir)
    manager.bootstrap_parent_trust(tmp_path / "runs")
    manager.cleanup_stale_entries([run_dir])

    op_names = [item[0] for item in calls]
    assert "register" in op_names
    assert "remove" in op_names
    assert op_names.count("bootstrap") == 2
    assert op_names.count("cleanup") == 2
