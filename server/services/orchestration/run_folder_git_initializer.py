from __future__ import annotations

import subprocess
from pathlib import Path


class RunFolderGitInitializer:
    def __init__(self, git_executable: str = "git") -> None:
        self.git_executable = git_executable

    def ensure_git_repo(self, run_dir: Path) -> bool:
        resolved = run_dir.resolve()
        git_dir = resolved / ".git"
        if git_dir.exists():
            return False
        resolved.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [self.git_executable, "init", "-q", str(resolved)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or "").strip() or (result.stdout or "").strip() or f"exit={result.returncode}"
            raise RuntimeError(f"Failed to initialize git repo for run folder {resolved}: {detail}")
        return True


run_folder_git_initializer = RunFolderGitInitializer()
