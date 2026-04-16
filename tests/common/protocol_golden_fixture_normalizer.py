from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_IGNORE_FIELDS = {
    "ts",
    "seq",
    "run_id",
    "request_id",
    "meta.local_seq",
    "correlation.publish_id",
    "correlation.request_id",
    "raw_ref.byte_from",
    "raw_ref.byte_to",
}


def _should_ignore(path_parts: tuple[str, ...], ignore_fields: set[str]) -> bool:
    if not path_parts:
        return False
    joined = ".".join(path_parts)
    leaf = path_parts[-1]
    return joined in ignore_fields or leaf in ignore_fields


def normalize_protocol_golden_value(
    value: Any,
    *,
    ignore_fields: Sequence[str] | None = None,
    _path_parts: tuple[str, ...] = (),
) -> Any:
    ignored = set(DEFAULT_IGNORE_FIELDS)
    if ignore_fields is not None:
        ignored.update(str(item) for item in ignore_fields if isinstance(item, str))

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            key_str = str(key)
            path_parts = (*_path_parts, key_str)
            if _should_ignore(path_parts, ignored):
                continue
            normalized[key_str] = normalize_protocol_golden_value(
                child,
                ignore_fields=tuple(ignored),
                _path_parts=path_parts,
            )
        return normalized

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            normalize_protocol_golden_value(
                child,
                ignore_fields=tuple(ignored),
                _path_parts=_path_parts,
            )
            for child in value
        ]

    return value


def normalize_rasp_event(event: Any, *, ignore_fields: Sequence[str] | None = None) -> dict[str, Any]:
    data = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
    normalized = normalize_protocol_golden_value(data, ignore_fields=ignore_fields)
    return {
        "type": normalized.get("event", {}).get("type"),
        "category": normalized.get("event", {}).get("category"),
        "data": normalized.get("data", {}),
        "source": normalized.get("source", {}),
        "correlation": normalized.get("correlation", {}),
        "raw_ref": normalized.get("raw_ref"),
    }


def normalize_fcmp_event(event: Any, *, ignore_fields: Sequence[str] | None = None) -> dict[str, Any]:
    data = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
    normalized = normalize_protocol_golden_value(data, ignore_fields=ignore_fields)
    return {
        "type": normalized.get("type"),
        "data": normalized.get("data", {}),
        "meta": normalized.get("meta", {}),
        "correlation": normalized.get("correlation", {}),
        "raw_ref": normalized.get("raw_ref"),
    }


def normalize_outcome_result(outcome: Any, *, ignore_fields: Sequence[str] | None = None) -> dict[str, Any]:
    data = outcome if isinstance(outcome, Mapping) else dict(vars(outcome))
    return normalize_protocol_golden_value(data, ignore_fields=ignore_fields)
