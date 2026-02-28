from __future__ import annotations

from server.runtime.protocol.event_protocol import (
    configure_runtime_parser_resolver,
    parse_engine_logs,
)


class _FakeAdapter:
    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes):
        _ = stdout_raw
        _ = stderr_raw
        _ = pty_raw
        return {
            "parser": "fake",
            "confidence": 0.95,
            "session_id": "session-1",
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": [],
            "structured_types": [],
        }


class _FakeResolver:
    def resolve(self, engine: str):
        if engine == "codex":
            return _FakeAdapter()
        return None


def test_runtime_protocol_uses_injected_parser_resolver() -> None:
    configure_runtime_parser_resolver(_FakeResolver())
    try:
        parsed = parse_engine_logs(engine="codex", stdout_raw=b"", stderr_raw=b"", pty_raw=b"")
        assert parsed["parser"] == "fake"
        assert parsed["session_id"] == "session-1"
    finally:
        configure_runtime_parser_resolver(None)
