from __future__ import annotations

import re
from collections.abc import Iterable


_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(
        r"(?i)([?&](?:access_token|token|code|secret)=)[^&#\s]+"
    ),
)


def _byte_mask(value: str) -> str:
    masks = {1: "*", 2: "¢", 3: "●", 4: "😀"}
    return "".join(masks[len(char.encode("utf-8"))] for char in value)


def redact_codebuddy_text(text: str, *, secrets: Iterable[str] = ()) -> str:
    """Redact secrets without changing the UTF-8 byte length of the stream."""
    redacted = text
    exact = sorted(
        {item for item in secrets if isinstance(item, str) and item},
        key=len,
        reverse=True,
    )
    for value in exact:
        redacted = redacted.replace(value, _byte_mask(value))
    for pattern in _PATTERNS:
        if pattern.groups:
            redacted = pattern.sub(
                lambda match: match.group(1) + _byte_mask(match.group(0)[len(match.group(1)) :]),
                redacted,
            )
        else:
            redacted = pattern.sub(lambda match: _byte_mask(match.group(0)), redacted)
    if len(redacted.encode("utf-8")) != len(text.encode("utf-8")):
        raise RuntimeError("CodeBuddy secret redaction changed stream byte length")
    return redacted


class CodeBuddySecretRedactor:
    """Stateful redactor that releases complete physical records immediately."""

    def __init__(self, *, secrets: Iterable[str], max_pending_bytes: int = 1024 * 1024) -> None:
        self._secrets = tuple(item for item in secrets if item)
        self._max_pending_bytes = max(1, int(max_pending_bytes))
        self._pending = ""

    def feed(self, text: str) -> str:
        self._pending += text
        record_end = self._pending.rfind("\n")
        if record_end < 0:
            self._ensure_pending_is_bounded()
            return ""
        split = record_end + 1
        ready = self._pending[:split]
        self._pending = self._pending[split:]
        self._ensure_pending_is_bounded()
        output = redact_codebuddy_text(ready, secrets=self._secrets)
        return output

    def flush(self) -> str:
        output = redact_codebuddy_text(self._pending, secrets=self._secrets)
        self._pending = ""
        return output

    def _ensure_pending_is_bounded(self) -> None:
        if len(self._pending.encode("utf-8")) > self._max_pending_bytes:
            raise RuntimeError("CodeBuddy secret redaction record exceeded the pending byte limit")
