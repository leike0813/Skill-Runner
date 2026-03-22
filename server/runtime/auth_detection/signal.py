from __future__ import annotations

from typing import Any, cast

from server.runtime.adapter.types import RuntimeAuthSignal
from server.runtime.auth_detection.types import AuthDetectionResult, AuthConfidence, AuthSubcategory

_ALLOWED_SUBCATEGORIES: set[AuthSubcategory] = {
    "oauth_reauth",
    "api_key_missing",
    "invalid_api_key",
    "auth_expired",
    "unknown_auth",
}


def is_high_confidence_auth_signal(auth_signal: RuntimeAuthSignal | None) -> bool:
    if not isinstance(auth_signal, dict):
        return False
    return bool(auth_signal.get("required")) and auth_signal.get("confidence") == "high"


def extract_auth_signal(runtime_parse_result: dict[str, Any] | None) -> RuntimeAuthSignal | None:
    if not isinstance(runtime_parse_result, dict):
        return None
    raw = runtime_parse_result.get("auth_signal")
    if not isinstance(raw, dict):
        return None
    required = bool(raw.get("required"))
    confidence = str(raw.get("confidence") or "").strip().lower()
    if confidence not in {"high", "low"}:
        confidence = "low"
    subcategory_obj = raw.get("subcategory")
    subcategory = subcategory_obj if isinstance(subcategory_obj, str) and subcategory_obj else None
    provider_obj = raw.get("provider_id")
    provider_id = provider_obj if isinstance(provider_obj, str) and provider_obj else None
    reason_obj = raw.get("reason_code")
    reason_code = reason_obj if isinstance(reason_obj, str) and reason_obj else None
    matched_obj = raw.get("matched_pattern_id")
    matched_pattern_id = matched_obj if isinstance(matched_obj, str) and matched_obj else None
    signal: RuntimeAuthSignal = {
        "required": required,
        "confidence": confidence,  # type: ignore[typeddict-item]
        "subcategory": subcategory,
        "provider_id": provider_id,
        "reason_code": reason_code,
        "matched_pattern_id": matched_pattern_id,
    }
    return signal


def is_high_confidence_auth_required(runtime_parse_result: dict[str, Any] | None) -> bool:
    signal = extract_auth_signal(runtime_parse_result)
    return is_high_confidence_auth_signal(signal)


def auth_detection_result_from_runtime_parse(
    *,
    engine: str,
    runtime_parse_result: dict[str, Any] | None,
) -> AuthDetectionResult:
    signal = extract_auth_signal(runtime_parse_result)
    if not isinstance(signal, dict):
        return AuthDetectionResult(
            classification="unknown",
            subcategory=None,
            confidence="low",
            engine=engine,
            provider_id=None,
            matched_rule_ids=[],
            evidence_sources=["combined"],
            evidence_excerpt=None,
            details={},
        )
    matched_pattern_id = signal.get("matched_pattern_id")
    matched_rule_ids = [matched_pattern_id] if isinstance(matched_pattern_id, str) and matched_pattern_id else []
    required = bool(signal.get("required"))
    confidence = signal.get("confidence")
    confidence_value: AuthConfidence = "high" if confidence == "high" else "low"
    provider_obj = signal.get("provider_id")
    provider_id = provider_obj if isinstance(provider_obj, str) and provider_obj else None
    subcategory_obj = signal.get("subcategory")
    subcategory: AuthSubcategory | None = None
    if isinstance(subcategory_obj, str) and subcategory_obj in _ALLOWED_SUBCATEGORIES:
        subcategory = cast(AuthSubcategory, subcategory_obj)
    details: dict[str, Any] = {}
    reason_obj = signal.get("reason_code")
    if isinstance(reason_obj, str) and reason_obj:
        details["reason_code"] = reason_obj
    return AuthDetectionResult(
        classification="auth_required" if required else "not_auth",
        subcategory=subcategory,
        confidence=confidence_value,
        engine=engine,
        provider_id=provider_id,
        matched_rule_ids=matched_rule_ids,
        evidence_sources=["parser_signal"],
        evidence_excerpt=None,
        details=details,
    )


def auth_detection_result_from_auth_signal(
    *,
    engine: str,
    auth_signal: RuntimeAuthSignal | None,
) -> AuthDetectionResult:
    runtime_parse_result: dict[str, Any] | None = None
    if isinstance(auth_signal, dict):
        runtime_parse_result = {"auth_signal": dict(auth_signal)}
    return auth_detection_result_from_runtime_parse(
        engine=engine,
        runtime_parse_result=runtime_parse_result,
    )
