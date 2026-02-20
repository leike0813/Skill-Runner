from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RecordingStore:
    """Persists per-run interaction traces for replay."""

    def __init__(self, recordings_dir: Path):
        self._recordings_dir = recordings_dir
        self._recordings_dir.mkdir(parents=True, exist_ok=True)

    def append_step(
        self,
        request_id: str,
        *,
        action: str,
        request_summary: Any | None = None,
        response_summary: Any | None = None,
        status: str = "ok",
    ) -> dict[str, Any]:
        payload = self._read_or_create(request_id)
        payload["updated_at"] = _utc_now_iso()
        steps = payload.setdefault("steps", [])
        if not isinstance(steps, list):
            steps = []
            payload["steps"] = steps
        steps.append(
            {
                "ts": _utc_now_iso(),
                "action": action,
                "status": status,
                "request": request_summary,
                "response": response_summary,
            }
        )
        self._write(request_id, payload)
        return payload

    def list_recordings(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._recordings_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            request_id = payload.get("request_id")
            steps = payload.get("steps")
            rows.append(
                {
                    "request_id": str(request_id or path.stem),
                    "updated_at": payload.get("updated_at"),
                    "step_count": len(steps) if isinstance(steps, list) else 0,
                }
            )
        return rows

    def get_recording(self, request_id: str) -> dict[str, Any]:
        path = self._path_for(request_id)
        if not path.exists():
            raise FileNotFoundError("Recording not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Recording payload is invalid")
        return payload

    def _read_or_create(self, request_id: str) -> dict[str, Any]:
        path = self._path_for(request_id)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        return {
            "request_id": request_id,
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "steps": [],
        }

    def _write(self, request_id: str, payload: dict[str, Any]) -> None:
        path = self._path_for(request_id)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path_for(self, request_id: str) -> Path:
        safe_id = "".join(
            ch for ch in request_id if ch.isalnum() or ch in {"-", "_", "."}
        )
        if not safe_id:
            raise ValueError("request_id is invalid")
        return self._recordings_dir / f"{safe_id}.json"


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

