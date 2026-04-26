from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

_JSON_EXCEPTIONS = (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError)


def claude_config_dir(agent_home: Path) -> Path:
    return agent_home / ".claude"


def active_claude_state_path(agent_home: Path) -> Path:
    return claude_config_dir(agent_home) / ".claude.json"


def legacy_claude_state_path(agent_home: Path) -> Path:
    return agent_home / ".claude.json"


def ensure_claude_active_state(
    agent_home: Path,
    *,
    bootstrap_payload: Mapping[str, Any] | None = None,
) -> Path:
    path = active_claude_state_path(agent_home)
    if path.exists():
        return path
    legacy_payload = _load_legacy_payload(legacy_claude_state_path(agent_home))
    payload: dict[str, Any] = dict(bootstrap_payload or {})
    payload.update(legacy_payload)
    write_claude_state_payload(path, payload)
    return path


def read_claude_state_payload(
    agent_home: Path,
    *,
    bootstrap_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    path = ensure_claude_active_state(agent_home, bootstrap_payload=bootstrap_payload)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Claude state must be a JSON object")
        return payload
    except _JSON_EXCEPTIONS:
        _backup_invalid_file(path)
        payload = dict(bootstrap_payload or {})
        write_claude_state_payload(path, payload)
        return payload


def write_claude_state_payload(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _load_legacy_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("legacy Claude state must be a JSON object")
        return payload
    except _JSON_EXCEPTIONS:
        _backup_invalid_file(path)
        return {}


def _backup_invalid_file(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.name}.invalid.bak")
    try:
        if backup.exists():
            backup.unlink()
        path.replace(backup)
    except OSError:
        pass
