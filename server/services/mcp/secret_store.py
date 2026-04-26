from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from server.config import config

_EMPTY_SECRETS_PAYLOAD: dict[str, Any] = {"version": 1, "secrets": {}}


@dataclass
class McpSecretStore:
    path: Path | None = None

    @property
    def secrets_path(self) -> Path:
        return self.path or Path(config.SYSTEM.MCP_SECRETS_FILE)

    def get_secret(self, secret_id: str) -> str | None:
        secrets = self._read_secrets()
        value = secrets.get(secret_id)
        if isinstance(value, str):
            return value
        return None

    def has_secret(self, secret_id: str) -> bool:
        return self.get_secret(secret_id) is not None

    def upsert_secret(self, secret_id: str, value: str) -> None:
        if not secret_id.strip():
            raise ValueError("secret_id is required")
        secrets = self._read_secrets()
        secrets[secret_id] = value
        self._write_payload({"version": 1, "secrets": secrets})

    def delete_secrets(self, secret_ids: set[str]) -> None:
        if not secret_ids:
            return
        secrets = self._read_secrets()
        changed = False
        for secret_id in secret_ids:
            if secret_id in secrets:
                del secrets[secret_id]
                changed = True
        if changed:
            self._write_payload({"version": 1, "secrets": secrets})

    def _read_secrets(self) -> dict[str, str]:
        path = self.secrets_path
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._backup_invalid_file(path)
            self._write_payload(_EMPTY_SECRETS_PAYLOAD)
            return {}
        if not isinstance(payload, dict):
            raise ValueError("MCP secret store must contain a JSON object")
        if payload.get("version") != 1:
            raise ValueError("MCP secret store version must be 1")
        raw_secrets = payload.get("secrets")
        if not isinstance(raw_secrets, dict):
            raise ValueError("MCP secret store secrets must be an object")
        secrets: dict[str, str] = {}
        for key, value in raw_secrets.items():
            if isinstance(key, str) and isinstance(value, str):
                secrets[key] = value
        return secrets

    def _write_payload(self, payload: Mapping[str, Any]) -> None:
        path = self.secrets_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _backup_invalid_file(path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_name(f"{path.name}.invalid.bak")
        if backup.exists():
            backup.unlink()
        path.replace(backup)


mcp_secret_store = McpSecretStore()
