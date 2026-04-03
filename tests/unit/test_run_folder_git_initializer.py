from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from server.services.orchestration.run_folder_git_initializer import RunFolderGitInitializer


def test_ensure_git_repo_initializes_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run-a"
    run_dir.mkdir(parents=True)
    commands: list[list[str]] = []

    def _fake_run(command, capture_output, check, text):  # type: ignore[no-untyped-def]
        commands.append(list(command))
        (run_dir / ".git").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("server.services.orchestration.run_folder_git_initializer.subprocess.run", _fake_run)
    initializer = RunFolderGitInitializer()

    created = initializer.ensure_git_repo(run_dir)

    assert created is True
    assert commands == [["git", "init", "-q", str(run_dir.resolve())]]
    assert (run_dir / ".git").exists()


def test_ensure_git_repo_is_idempotent_when_git_dir_exists(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-b"
    (run_dir / ".git").mkdir(parents=True)
    initializer = RunFolderGitInitializer()

    created = initializer.ensure_git_repo(run_dir)

    assert created is False


def test_ensure_git_repo_raises_on_git_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "run-c"
    run_dir.mkdir(parents=True)

    def _fake_run(command, capture_output, check, text):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(command, 1, "", "git init failed")

    monkeypatch.setattr("server.services.orchestration.run_folder_git_initializer.subprocess.run", _fake_run)
    initializer = RunFolderGitInitializer()

    with pytest.raises(RuntimeError, match="git init failed"):
        initializer.ensure_git_repo(run_dir)
