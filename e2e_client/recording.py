from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any

RUN_SOURCE_INSTALLED = "installed"
RUN_SOURCE_TEMP = "temp"
_RUN_SOURCES = {RUN_SOURCE_INSTALLED, RUN_SOURCE_TEMP}


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
        run_source: str | None = None,
        request_summary: Any | None = None,
        response_summary: Any | None = None,
        status: str = "ok",
    ) -> dict[str, Any]:
        payload = self._read_or_create(request_id)
        if isinstance(run_source, str) and run_source in _RUN_SOURCES:
            payload["run_source"] = run_source
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

    def update_observation_summary(
        self,
        request_id: str,
        *,
        run_source: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._read_or_create(request_id)
        if isinstance(run_source, str) and run_source in _RUN_SOURCES:
            payload["run_source"] = run_source
        payload["updated_at"] = _utc_now_iso()
        merged = _merge_observation_summary(
            payload.get("observation_summary"),
            summary or {},
        )
        payload["observation_summary"] = merged
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
                    "created_at": payload.get("created_at"),
                    "updated_at": payload.get("updated_at"),
                    "step_count": len(steps) if isinstance(steps, list) else 0,
                    "run_source": (
                        payload.get("run_source")
                        if payload.get("run_source") in _RUN_SOURCES
                        else RUN_SOURCE_INSTALLED
                    ),
                }
            )
        rows.sort(key=_recording_row_sort_key, reverse=True)
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
            "run_source": RUN_SOURCE_INSTALLED,
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


def _parse_iso_to_epoch(raw: Any) -> float | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def _recording_row_sort_key(row: dict[str, Any]) -> tuple[float, str]:
    created_at = _parse_iso_to_epoch(row.get("created_at"))
    updated_at = _parse_iso_to_epoch(row.get("updated_at"))
    ts = created_at if created_at is not None else (updated_at or float("-inf"))
    return ts, str(row.get("request_id") or "")


def _merge_observation_summary(existing: Any, incoming: dict[str, Any]) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    result: dict[str, Any] = {
        "cursor": _safe_non_negative_int(base.get("cursor")),
        "last_chat_event": base.get("last_chat_event") if isinstance(base.get("last_chat_event"), dict) else {},
        "key_events": _coerce_dict_list(base.get("key_events")),
        "raw_refs": _coerce_dict_list(base.get("raw_refs")),
        "updated_at": _utc_now_iso(),
    }

    incoming_cursor = _safe_non_negative_int(incoming.get("cursor"))
    if incoming_cursor > result["cursor"]:
        result["cursor"] = incoming_cursor

    incoming_last = incoming.get("last_chat_event")
    if isinstance(incoming_last, dict):
        result["last_chat_event"] = incoming_last

    incoming_events = _coerce_dict_list(incoming.get("key_events"))
    incoming_refs = _coerce_dict_list(incoming.get("raw_refs"))
    result["key_events"] = _merge_unique_dict_rows(
        result["key_events"],
        incoming_events,
        key_builder=_key_event_identity,
        limit=30,
    )
    result["raw_refs"] = _merge_unique_dict_rows(
        result["raw_refs"],
        incoming_refs,
        key_builder=_raw_ref_identity,
        limit=30,
    )
    return result


def _safe_non_negative_int(raw: Any) -> int:
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return raw if raw >= 0 else 0
    if isinstance(raw, float):
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return 0
        return value if value >= 0 else 0
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return 0
        try:
            value = int(text)
        except ValueError:
            return 0
        return value if value >= 0 else 0
    return 0


def _coerce_dict_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _merge_unique_dict_rows(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    key_builder: Callable[[dict[str, Any]], str],
    limit: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in existing + incoming:
        key = key_builder(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    if len(merged) > limit:
        return merged[-limit:]
    return merged


def _key_event_identity(row: dict[str, Any]) -> str:
    seq = str(_safe_non_negative_int(row.get("seq")))
    event_type = str(row.get("type") or "")
    correlation = str(row.get("correlation") or "")
    return f"{seq}|{event_type}|{correlation}"


def _raw_ref_identity(row: dict[str, Any]) -> str:
    stream = str(row.get("stream") or "")
    byte_from = str(_safe_non_negative_int(row.get("byte_from")))
    byte_to = str(_safe_non_negative_int(row.get("byte_to")))
    return f"{stream}|{byte_from}|{byte_to}"
