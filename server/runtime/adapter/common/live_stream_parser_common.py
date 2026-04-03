from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from server.runtime.adapter.types import LiveParserEmission, RuntimeStreamRawRef
from server.runtime.protocol.contracts import LiveStreamParserSession


class NdjsonLiveStreamParserSession(LiveStreamParserSession, ABC):
    def __init__(self, *, accepted_streams: set[str] | None = None) -> None:
        self._accepted_streams = set(accepted_streams or {"stdout", "pty"})
        self._buffers: dict[str, str] = {stream: "" for stream in self._accepted_streams}
        self._buffer_byte_start: dict[str, int] = {stream: 0 for stream in self._accepted_streams}

    @abstractmethod
    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        raise NotImplementedError

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        return []

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        if stream not in self._accepted_streams:
            return []
        previous_tail = self._buffers.get(stream, "")
        previous_tail_start = self._buffer_byte_start.get(stream, int(byte_from))
        if previous_tail:
            combined = f"{previous_tail}{text}"
            combined_start = previous_tail_start
        else:
            combined = text
            combined_start = int(byte_from)
        if "\n" not in combined:
            self._buffers[stream] = combined
            self._buffer_byte_start[stream] = combined_start
            return []

        lines = combined.splitlines(keepends=True)
        complete = lines[:-1]
        tail = lines[-1]
        if tail.endswith("\n"):
            complete.append(tail)
            tail = ""

        self._buffers[stream] = tail
        cursor = combined_start
        self._buffer_byte_start[stream] = cursor
        emissions: list[LiveParserEmission] = []
        for line in complete:
            clean = line.strip()
            encoded = line.encode("utf-8", errors="replace")
            row_from = cursor
            row_to = cursor + len(encoded)
            cursor = row_to
            self._buffer_byte_start[stream] = cursor
            if not clean:
                continue
            try:
                payload = json.loads(clean)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            emissions.extend(
                self.handle_live_row(
                    payload=payload,
                    raw_ref={
                        "stream": stream,
                        "byte_from": row_from,
                        "byte_to": row_to,
                    },
                    stream=stream,
                )
            )
        if tail:
            self._buffer_byte_start[stream] = cursor
        else:
            self._buffer_byte_start[stream] = int(byte_to)
        return emissions
