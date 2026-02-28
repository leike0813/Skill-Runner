import json
from pathlib import Path

import tomlkit

from server.services.orchestration.run_folder_trust_manager import RunFolderTrustManager


def _load_toml(path: Path):
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def test_codex_register_and_remove_run_folder(tmp_path):
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "run-a"
    run_dir.mkdir(parents=True)
    codex_path = tmp_path / "codex" / "config.toml"
    gemini_path = tmp_path / "gemini" / "trustedFolders.json"
    manager = RunFolderTrustManager(
        codex_config_path=codex_path,
        gemini_trusted_path=gemini_path,
        runs_root=runs_root,
    )

    manager.register_run_folder("codex", run_dir)
    doc = _load_toml(codex_path)
    assert doc["projects"][str(run_dir.resolve())]["trust_level"] == "trusted"

    manager.remove_run_folder("codex", run_dir)
    doc = _load_toml(codex_path)
    assert str(run_dir.resolve()) not in doc.get("projects", {})


def test_gemini_register_repairs_malformed_file(tmp_path):
    runs_root = tmp_path / "runs"
    run_dir = runs_root / "run-b"
    run_dir.mkdir(parents=True)
    codex_path = tmp_path / "codex" / "config.toml"
    gemini_path = tmp_path / "gemini" / "trustedFolders.json"
    gemini_path.parent.mkdir(parents=True, exist_ok=True)
    gemini_path.write_text("not-json", encoding="utf-8")
    manager = RunFolderTrustManager(
        codex_config_path=codex_path,
        gemini_trusted_path=gemini_path,
        runs_root=runs_root,
    )

    manager.register_run_folder("gemini", run_dir)
    payload = json.loads(gemini_path.read_text(encoding="utf-8"))
    assert payload[str(run_dir.resolve())] == "TRUST_FOLDER"
    assert gemini_path.with_name("trustedFolders.json.bak").exists()


def test_cleanup_stale_entries_only_removes_inactive_run_paths(tmp_path):
    runs_root = tmp_path / "runs"
    active_dir = runs_root / "run-active"
    stale_dir = runs_root / "run-stale"
    active_dir.mkdir(parents=True)
    stale_dir.mkdir(parents=True)
    codex_path = tmp_path / "codex" / "config.toml"
    gemini_path = tmp_path / "gemini" / "trustedFolders.json"
    manager = RunFolderTrustManager(
        codex_config_path=codex_path,
        gemini_trusted_path=gemini_path,
        runs_root=runs_root,
    )

    manager.bootstrap_parent_trust(runs_root)
    manager.register_run_folder("codex", active_dir)
    manager.register_run_folder("codex", stale_dir)
    manager.register_run_folder("gemini", active_dir)
    manager.register_run_folder("gemini", stale_dir)

    manager.cleanup_stale_entries([active_dir])

    doc = _load_toml(codex_path)
    projects = doc.get("projects", {})
    assert str(active_dir.resolve()) in projects
    assert str(stale_dir.resolve()) not in projects
    assert str(runs_root.resolve()) in projects

    payload = json.loads(gemini_path.read_text(encoding="utf-8"))
    assert str(active_dir.resolve()) in payload
    assert str(stale_dir.resolve()) not in payload
    assert str(runs_root.resolve()) in payload


def test_bootstrap_parent_trust_is_idempotent(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True)
    codex_path = tmp_path / "codex" / "config.toml"
    gemini_path = tmp_path / "gemini" / "trustedFolders.json"
    manager = RunFolderTrustManager(
        codex_config_path=codex_path,
        gemini_trusted_path=gemini_path,
        runs_root=runs_root,
    )

    manager.bootstrap_parent_trust(runs_root)
    manager.bootstrap_parent_trust(runs_root)

    doc = _load_toml(codex_path)
    projects = doc.get("projects", {})
    parent_key = str(runs_root.resolve())
    assert parent_key in projects
    assert projects[parent_key]["trust_level"] == "trusted"
    assert list(projects.keys()).count(parent_key) == 1

    payload = json.loads(gemini_path.read_text(encoding="utf-8"))
    assert payload[parent_key] == "TRUST_FOLDER"
    assert len([k for k in payload if k == parent_key]) == 1
