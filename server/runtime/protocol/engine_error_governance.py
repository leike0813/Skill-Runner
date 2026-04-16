from __future__ import annotations

from typing import Any


def _normalize_text(value: Any) -> str | None:
    if isinstance(value, str):
        compact = " ".join(value.replace("\r", "\n").split())
        return compact.strip() or None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def classify_engine_message_pattern(
    message: str | None,
    *,
    default_code: str,
    default_pattern_kind: str,
) -> tuple[str, str, str]:
    normalized = _normalize_text(message)
    if not normalized:
        return default_code, default_pattern_kind, "warning"
    lower = normalized.lower()
    if "deprecated" in lower or "will be removed" in lower:
        return "ENGINE_DEPRECATION_WARNING", "engine_deprecation_warning", "warning"
    if any(token in lower for token in ("usage limit", "rate limit", "quota exceeded", "too many requests")):
        return "ENGINE_RATE_LIMIT_HINT", "engine_rate_limit_hint", "warning"
    if any(
        token in lower
        for token in (
            "auth",
            "authentication",
            "unauthorized",
            "logged out",
            "sign in again",
            "api key",
            "token",
            "login",
        )
    ):
        return "ENGINE_AUTH_HINT", "engine_auth_hint", "warning"
    return default_code, default_pattern_kind, "warning"


def extract_turn_failed_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if str(payload.get("type") or "") != "turn.failed":
        return None
    error_obj = payload.get("error")
    message = None
    code = None
    if isinstance(error_obj, dict):
        message = _normalize_text(error_obj.get("message"))
        code = _normalize_text(error_obj.get("code"))
    if message is None:
        message = _normalize_text(payload.get("message"))
    pattern_code, pattern_kind, _severity = classify_engine_message_pattern(
        message,
        default_code=(code or "ENGINE_TURN_FAILED"),
        default_pattern_kind="engine_turn_failed",
    )
    result: dict[str, Any] = {
        "message": message or "turn failed",
        "source_type": "turn.failed",
        "pattern_kind": pattern_kind,
        "fatal": True,
    }
    if code is not None:
        result["code"] = code
    elif pattern_code:
        result["code"] = pattern_code
    return result


def classify_engine_error_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    payload_type = str(payload.get("type") or "")
    message: str | None = None
    source_type: str | None = None
    default_code: str
    default_pattern_kind: str

    if payload_type == "error":
        message = _normalize_text(payload.get("message"))
        source_type = "type:error"
        default_code = "ENGINE_ERROR_ROW"
        default_pattern_kind = "engine_error_row"
    elif payload_type == "item.completed":
        item = payload.get("item")
        if not isinstance(item, dict) or str(item.get("type") or "") != "error":
            return None
        message = (
            _normalize_text(item.get("message"))
            or _normalize_text(item.get("text"))
            or _normalize_text(item.get("content"))
        )
        source_type = "item.type:error"
        default_code = "ENGINE_ERROR_ITEM"
        default_pattern_kind = "engine_error_item"
    else:
        return None

    code, pattern_kind, severity = classify_engine_message_pattern(
        message,
        default_code=default_code,
        default_pattern_kind=default_pattern_kind,
    )
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "pattern_kind": pattern_kind,
        "source_type": source_type,
        "authoritative": False,
    }
    if message is not None:
        result["message"] = message
        result["detail"] = message
    return result
