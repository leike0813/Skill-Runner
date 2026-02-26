from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict


class OpencodeAuthStore:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def auth_path(self) -> Path:
        return self.agent_home / ".local" / "share" / "opencode" / "auth.json"

    @property
    def antigravity_accounts_path(self) -> Path:
        return self.agent_home / ".config" / "opencode" / "antigravity-accounts.json"

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw) if raw.strip() else {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _write_json_atomic(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        self._write_text_atomic(path, content)

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = ""
        with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            os.replace(tmp_path, path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def backup_antigravity_accounts(self, backup_path: Path) -> Dict[str, Any]:
        source = self.antigravity_accounts_path
        if not source.exists():
            return {
                "source_exists": False,
                "backup_created": False,
                "backup_path": None,
            }
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(backup_path, source.read_text(encoding="utf-8"))
        return {
            "source_exists": True,
            "backup_created": True,
            "backup_path": str(backup_path),
        }

    def restore_antigravity_accounts(
        self,
        *,
        source_exists: bool,
        backup_path: str | None = None,
    ) -> None:
        target = self.antigravity_accounts_path
        if not source_exists:
            if target.exists():
                target.unlink()
            return
        if not backup_path:
            raise ValueError("backup_path is required when source_exists is True")
        backup = Path(backup_path)
        if not backup.exists():
            raise ValueError(f"backup file not found: {backup}")
        self._write_text_atomic(target, backup.read_text(encoding="utf-8"))

    def upsert_api_key(self, provider_id: str, api_key: str) -> None:
        normalized_provider = provider_id.strip().lower()
        normalized_key = api_key.strip()
        if not normalized_provider:
            raise ValueError("provider_id is required")
        if not normalized_key:
            raise ValueError("API key is required")

        payload = self._read_json(self.auth_path)
        payload[normalized_provider] = {
            "type": "api",
            "key": normalized_key,
        }
        self._write_json_atomic(self.auth_path, payload)

    def clear_antigravity_accounts(self) -> Dict[str, Any]:
        path = self.antigravity_accounts_path
        payload = self._read_json(path)
        accounts = payload.get("accounts")
        removed = len(accounts) if isinstance(accounts, list) else 0
        payload["accounts"] = []

        if "active" in payload:
            payload["active"] = None
        if "activeIndex" in payload:
            payload["activeIndex"] = -1
        if "selected" in payload:
            payload["selected"] = None

        self._write_json_atomic(path, payload)
        return {
            "path": str(path),
            "removed_accounts": removed,
        }
