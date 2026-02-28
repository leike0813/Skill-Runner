from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_SESSION_TIMEOUT_SEC = 1200
INTERACTIVE_REPLY_TIMEOUT_KEY = "interactive_reply_timeout_sec"


@dataclass(frozen=True)
class SessionTimeoutResolution:
    value: int
    source: str


def resolve_interactive_reply_timeout(
    options: Mapping[str, Any],
    default: int = DEFAULT_SESSION_TIMEOUT_SEC,
) -> SessionTimeoutResolution:
    preferred = _parse_positive_int(options.get(INTERACTIVE_REPLY_TIMEOUT_KEY))
    if preferred is not None:
        return SessionTimeoutResolution(
            value=preferred,
            source=INTERACTIVE_REPLY_TIMEOUT_KEY,
        )
    return SessionTimeoutResolution(
        value=max(1, int(default)),
        source="default",
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
