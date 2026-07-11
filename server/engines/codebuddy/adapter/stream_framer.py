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
        self._pending = ""
        self._pending_start = 0

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

    @staticmethod
    def _is_object(raw: str) -> bool:
        try:
            return isinstance(json.loads(raw.strip()), dict)
        except json.JSONDecodeError:
            return False

    @staticmethod
    def _may_continue(raw: str) -> bool:
        in_string = False
        escape = False
        for char in raw.rstrip("\r\n"):
            if escape:
                escape = False
            elif char == "\\" and in_string:
                escape = True
            elif char == '"':
                in_string = not in_string
        return in_string

    def _consume_physical_line(self, raw: str, start: int, end: int) -> list[CodeBuddyFrame]:
        if not self._pending:
            frame = self._frame(raw, start, end)
            if frame.payload is not None or not self._may_continue(raw):
                return [frame]
            self._pending = raw
            self._pending_start = start
            return []

        combined = self._pending + raw
        combined_frame = self._frame(combined, self._pending_start, end)
        if combined_frame.payload is not None:
            self._pending = ""
            return [combined_frame]

        if self._is_object(raw):
            pending = CodeBuddyFrame(
                None,
                self._pending,
                self._pending_start,
                start,
                diagnostic="CODEBUDDY_FRAME_UNTERMINATED",
                repaired=True,
            )
            self._pending = ""
            return [pending, self._frame(raw, start, end)]

        self._pending = combined
        if len(combined.encode("utf-8", errors="replace")) > self._line_limit:
            self._pending = ""
            return [
                CodeBuddyFrame(
                    None,
                    combined,
                    self._pending_start,
                    end,
                    diagnostic="CODEBUDDY_FRAME_OVER_LIMIT",
                    repaired=True,
                )
            ]
        return []

    def feed(self, text: str) -> list[CodeBuddyFrame]:
        self._buffer += text
        frames: list[CodeBuddyFrame] = []
        while True:
            newline = self._buffer.find("\n")
            if newline < 0:
                break
            record_end = newline + 1
            raw = self._buffer[:record_end]
            self._buffer = self._buffer[record_end:]
            start = self._offset
            self._offset += len(raw.encode("utf-8", errors="replace"))
            frames.extend(self._consume_physical_line(raw, start, self._offset))
        return frames

    def finish(self) -> list[CodeBuddyFrame]:
        raw = self._buffer
        self._buffer = ""
        start = self._offset
        self._offset += len(raw.encode("utf-8", errors="replace"))
        frames: list[CodeBuddyFrame] = []
        if raw:
            frames.extend(self._consume_physical_line(raw, start, self._offset))
        if self._pending:
            pending = self._pending
            pending_start = self._pending_start
            self._pending = ""
            frame = self._frame(pending, pending_start, self._offset)
            if frame.payload is not None:
                frames.append(frame)
            else:
                frames.append(
                    CodeBuddyFrame(
                        None,
                        pending,
                        pending_start,
                        self._offset,
                        diagnostic="CODEBUDDY_FRAME_UNTERMINATED",
                        repaired=frame.repaired,
                    )
                )
        return frames
