from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodeBuddyFrame:
    payload: dict[str, Any] | None
    raw: str
    byte_from: int
    byte_to: int
    diagnostic: str | None = None
    repaired: bool = False


class CodeBuddyStreamFramer:
    """Bounded JSONL framer that repairs physical newlines inside JSON strings."""
    def __init__(self, *, line_limit: int = 1024 * 1024) -> None:
        self._buffer = ""
        self._offset = 0
        self._line_limit = line_limit

    @staticmethod
    def _repair(candidate: str) -> tuple[str, bool]:
        result: list[str] = []
        in_string = False
        escape = False
        repaired = False
        for char in candidate:
            if in_string and char in "\r\n":
                if char == "\n":
                    result.append("\\n")
                    repaired = True
                continue
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = not in_string
        return "".join(result), repaired

    def _frame(self, raw: str, start: int, end: int) -> CodeBuddyFrame:
        candidate, repaired = self._repair(raw.rstrip("\r\n"))
        if len(raw.encode("utf-8", errors="replace")) > self._line_limit:
            return CodeBuddyFrame(None, raw, start, end, diagnostic="CODEBUDDY_FRAME_OVER_LIMIT")
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return CodeBuddyFrame(None, raw, start, end, diagnostic="CODEBUDDY_FRAME_MALFORMED", repaired=repaired)
        if not isinstance(payload, dict):
            return CodeBuddyFrame(None, raw, start, end, diagnostic="CODEBUDDY_FRAME_NOT_OBJECT", repaired=repaired)
        return CodeBuddyFrame(payload, raw, start, end, repaired=repaired)

    def feed(self, text: str) -> list[CodeBuddyFrame]:
        self._buffer += text
        frames: list[CodeBuddyFrame] = []
        while "\n" in self._buffer:
            row, self._buffer = self._buffer.split("\n", 1)
            raw = f"{row}\n"
            start = self._offset
            self._offset += len(raw.encode("utf-8", errors="replace"))
            frames.append(self._frame(raw, start, self._offset))
        return frames

    def finish(self) -> list[CodeBuddyFrame]:
        if not self._buffer:
            return []
        raw = self._buffer
        self._buffer = ""
        start = self._offset
        self._offset += len(raw.encode("utf-8", errors="replace"))
        frame = self._frame(raw, start, self._offset)
        if frame.payload is None:
            return [CodeBuddyFrame(None, raw, start, self._offset, diagnostic="CODEBUDDY_FRAME_UNTERMINATED", repaired=frame.repaired)]
        return [frame]
