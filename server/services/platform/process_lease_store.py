from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import config

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProcessLeaseStore:
    def __init__(self, lease_dir: Path | None = None) -> None:
        base = lease_dir or (Path(config.SYSTEM.DATA_DIR) / "runtime_process_leases")
        self._lease_dir = base

    @property
    def lease_dir(self) -> Path:
        return self._lease_dir

    def ensure_dir(self) -> Path:
        self._lease_dir.mkdir(parents=True, exist_ok=True)
        return self._lease_dir

    def _lease_path(self, lease_id: str) -> Path:
        safe = lease_id.strip()
        if not safe:
            raise ValueError("lease_id is required")
        return self.ensure_dir() / f"{safe}.json"

    def _read_payload(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("Process lease read failed: %s", path, exc_info=True)
            return None
        if not isinstance(payload, dict):
            logger.warning("Process lease payload is not an object: %s", path)
            return None
        return payload

    def _write_payload(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)

    def upsert_active(self, lease_payload: dict[str, Any]) -> None:
        lease_id_raw = lease_payload.get("lease_id")
        if not isinstance(lease_id_raw, str) or not lease_id_raw.strip():
            raise ValueError("lease_payload.lease_id is required")
        payload = dict(lease_payload)
        payload["status"] = "active"
        payload.setdefault("updated_at", _utc_now_iso())
        payload.setdefault("created_at", payload["updated_at"])
        self._write_payload(self._lease_path(lease_id_raw), payload)

    def get(self, lease_id: str) -> dict[str, Any] | None:
        return self._read_payload(self._lease_path(lease_id))

    def close(self, lease_id: str, *, reason: str, closed_at: str | None = None) -> None:
        path = self._lease_path(lease_id)
        payload = self._read_payload(path)
        if payload is None:
            return
        payload["status"] = "closed"
        payload["close_reason"] = reason
        payload["closed_at"] = closed_at or _utc_now_iso()
        payload["updated_at"] = payload["closed_at"]
        self._write_payload(path, payload)

    def list_active(self) -> list[dict[str, Any]]:
        if not self._lease_dir.exists():
            return []
        active: list[dict[str, Any]] = []
        for path in sorted(self._lease_dir.glob("*.json")):
            payload = self._read_payload(path)
            if payload is None:
                continue
            if str(payload.get("status") or "").strip().lower() != "active":
                continue
            active.append(payload)
        return active


process_lease_store = ProcessLeaseStore()
