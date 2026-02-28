from __future__ import annotations

import json
import re
from typing import Any, Callable

from ....models import EngineSessionHandle, EngineSessionHandleType
from ....runtime.protocol.parse_utils import find_session_id, find_session_id_in_text
from .profile_loader import AdapterProfile

def first_json_line(raw_stdout: str, *, error_prefix: str) -> dict[str, Any]:
    for line in raw_stdout.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{error_prefix}: invalid json stream") from exc
        if isinstance(payload, dict):
            return payload
        raise RuntimeError(f"{error_prefix}: first event must be object")
    raise RuntimeError(f"{error_prefix}: output is empty")


def scan_json_lines_for_session_id(
    raw_stdout: str,
    *,
    finder: Callable[[dict[str, Any]], str | None],
    error_prefix: str,
) -> str:
    for line in raw_stdout.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{error_prefix}: invalid json stream") from exc
        if not isinstance(payload, dict):
            continue
        session_id = finder(payload)
        if isinstance(session_id, str) and session_id.strip():
            return session_id.strip()
    raise RuntimeError(f"{error_prefix}: missing session id")


def extract_by_regex(raw_stdout: str, *, pattern: str, error_message: str) -> str:
    match = re.search(pattern, raw_stdout)
    if not match:
        raise RuntimeError(error_message)
    value = match.group(1).strip()
    if not value:
        raise RuntimeError(error_message)
    return value


def _find_recursive_value(payload: Any, key: str) -> str | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        for child in payload.values():
            found = _find_recursive_value(child, key)
            if found:
                return found
        return None
    if isinstance(payload, list):
        for child in payload:
            found = _find_recursive_value(child, key)
            if found:
                return found
    return None


class ProfiledSessionCodec:
    def __init__(self, *, profile: AdapterProfile) -> None:
        self._profile = profile

    def extract(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        codec = self._profile.session_codec
        strategy = codec.strategy
        session_id: str | None = None

        if strategy == "first_json_line":
            event = first_json_line(
                raw_stdout,
                error_prefix=codec.error_prefix or "SESSION_RESUME_FAILED",
            )
            required_type = codec.required_type
            if required_type and event.get("type") != required_type:
                raise RuntimeError(codec.error_message)
            field_name = codec.id_field or "session_id"
            value = event.get(field_name)
            if isinstance(value, str) and value.strip():
                session_id = value.strip()

        elif strategy == "json_lines_scan":
            finder_name = codec.json_lines_finder
            if finder_name != "find_session_id":
                raise RuntimeError(f"Unsupported json_lines finder: {finder_name}")
            session_id = scan_json_lines_for_session_id(
                raw_stdout,
                finder=find_session_id,
                error_prefix=codec.error_prefix or "SESSION_RESUME_FAILED",
            )

        elif strategy == "regex_extract":
            pattern = codec.regex_pattern
            if not isinstance(pattern, str) or not pattern:
                raise RuntimeError("SESSION_RESUME_FAILED: regex pattern is not configured")
            session_id = extract_by_regex(
                raw_stdout,
                pattern=pattern,
                error_message=codec.error_message,
            )

        elif strategy == "json_recursive_key":
            recursive_key = codec.recursive_key or "session_id"
            try:
                payload = json.loads(raw_stdout)
            except json.JSONDecodeError:
                payload = None
            if payload is not None:
                session_id = _find_recursive_value(payload, recursive_key)
            if not session_id and codec.fallback_text_finder == "find_session_id_in_text":
                session_id = find_session_id_in_text(raw_stdout)

        else:
            raise RuntimeError(f"Unsupported session codec strategy: {strategy}")

        if not isinstance(session_id, str) or not session_id.strip():
            raise RuntimeError(codec.error_message)

        return EngineSessionHandle(
            engine=self._profile.engine,
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=session_id.strip(),
            created_at_turn=turn_index,
        )
