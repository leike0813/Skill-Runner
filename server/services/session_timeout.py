from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_SESSION_TIMEOUT_SEC = 1200
SESSION_TIMEOUT_KEY = "session_timeout_sec"
LEGACY_SESSION_TIMEOUT_KEYS = (
    "interactive_wait_timeout_sec",
    "hard_wait_timeout_sec",
    "wait_timeout_sec",
)


@dataclass(frozen=True)
class SessionTimeoutResolution:
    value: int
    source: str
    deprecated_keys_used: tuple[str, ...]
    legacy_keys_ignored: tuple[str, ...]


def resolve_session_timeout(
    options: Mapping[str, Any],
    default: int = DEFAULT_SESSION_TIMEOUT_SEC,
) -> SessionTimeoutResolution:
    preferred = _parse_positive_int(options.get(SESSION_TIMEOUT_KEY))
    deprecated_used: list[str] = []
    ignored_legacy: list[str] = []

    legacy_value = None
    for key in LEGACY_SESSION_TIMEOUT_KEYS:
        candidate = _parse_positive_int(options.get(key))
        if candidate is None:
            continue
        if preferred is not None:
            ignored_legacy.append(key)
            continue
        deprecated_used.append(key)
        if legacy_value is None:
            legacy_value = candidate

    if preferred is not None:
        return SessionTimeoutResolution(
            value=preferred,
            source=SESSION_TIMEOUT_KEY,
            deprecated_keys_used=tuple(deprecated_used),
            legacy_keys_ignored=tuple(ignored_legacy),
        )
    if legacy_value is not None:
        return SessionTimeoutResolution(
            value=legacy_value,
            source="legacy",
            deprecated_keys_used=tuple(deprecated_used),
            legacy_keys_ignored=tuple(ignored_legacy),
        )
    return SessionTimeoutResolution(
        value=max(1, int(default)),
        source="default",
        deprecated_keys_used=tuple(deprecated_used),
        legacy_keys_ignored=tuple(ignored_legacy),
    )


def _parse_positive_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed
