from __future__ import annotations

import codecs


class IncrementalUtf8TextDecoder:
    """Incrementally decode UTF-8 bytes without corrupting split multibyte characters."""

    def __init__(self) -> None:
        factory = codecs.getincrementaldecoder("utf-8")
        self._decoder = factory(errors="replace")

    def feed(self, chunk: bytes) -> str:
        if not chunk:
            return ""
        return str(self._decoder.decode(chunk, final=False))

    def finish(self) -> tuple[str, int]:
        state = self._decoder.getstate()
        pending_len = 0
        if isinstance(state, tuple) and state:
            pending = state[0]
            if isinstance(pending, (bytes, bytearray)):
                pending_len = len(pending)
        return str(self._decoder.decode(b"", final=True)), pending_len
