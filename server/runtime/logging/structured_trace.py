from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from .run_context import get_logging_context

_SENSITIVE_KEYS = {
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization_code",
    "callback_url",
    "submission_value",
    "credential",
    "secret",
}


def _format_value(value: Any) -> str:
    if isinstance(value, (int, float, bool)):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _is_sensitive(key: str) -> bool:
    lowered = key.strip().lower()
    if lowered in _SENSITIVE_KEYS:
        return True
    return any(marker in lowered for marker in ("token", "secret", "password", "credential"))


def _sanitize_value(key: str, value: Any) -> Any:
    if not _is_sensitive(key):
        return value
    if value is None:
        return None
    raw = str(value)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"<redacted:len={len(raw)}:sha256={digest}>"


def _normalize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        normalized[key] = _sanitize_value(key, value)
    return normalized


def log_event(
    logger: logging.Logger,
    *,
    event: str,
    phase: str,
    outcome: str,
    level: int = logging.INFO,
    request_id: str | None = None,
    run_id: str | None = None,
    attempt: int | None = None,
    error_code: str | None = None,
    error_type: str | None = None,
    **fields: Any,
) -> None:
    context = get_logging_context()
    payload: dict[str, Any] = {
        "event": event,
        "request_id": request_id or context.get("request_id"),
        "run_id": run_id or context.get("run_id"),
        "attempt": attempt if attempt is not None else context.get("attempt_number"),
        "phase": phase,
        "outcome": outcome,
        "error_code": error_code,
        "error_type": error_type,
        **fields,
    }
    serialized = _normalize_fields(payload)
    message = " ".join(
        f"{key}={_format_value(serialized[key])}" for key in sorted(serialized.keys())
    )
    logger.log(level, message)
