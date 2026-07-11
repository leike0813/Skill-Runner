from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from server.config import config
from server.engines.codebuddy.auth.provider_registry import require_provider


def credential_vault_path() -> Path:
    return Path(config.SYSTEM.DATA_DIR) / "engine_credentials" / "codebuddy.json"


def runtime_root(agent_home: Path | None = None) -> Path:
    return Path(agent_home or config.SYSTEM.AGENT_HOME) / ".codebuddy-runtime"


def provider_runtime_dir(provider_id: str, agent_home: Path | None = None) -> Path:
    require_provider(provider_id)
    return runtime_root(agent_home) / provider_id


def assert_no_symlink(path: Path) -> None:
    current = path
    existing: list[Path] = []
    while True:
        if current.exists() or current.is_symlink():
            existing.append(current)
        if current == current.parent:
            break
        current = current.parent
    for item in existing:
        if item.is_symlink():
            raise ValueError(f"CodeBuddy managed path must not contain symlinks: {item}")


def ensure_private_dir(path: Path) -> Path:
    assert_no_symlink(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    assert_no_symlink(path)
    os.chmod(path, 0o700)
    return path


def atomic_write_text(path: Path, text: str) -> None:
    ensure_private_dir(path.parent)
    assert_no_symlink(path)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(raw_tmp)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        assert_no_symlink(path)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
