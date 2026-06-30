from __future__ import annotations

from pathlib import Path

import pytest

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.kilo.adapter.execution_adapter import KiloExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.services.engine_management.engine_adapter_registry import EngineAdapterRegistry


def test_registry_exposes_all_supported_adapters() -> None:
    registry = EngineAdapterRegistry()
    adapters = registry.adapter_map()

    assert set(adapters.keys()) == {"codex", "opencode", "claude", "qwen", "kilo"}
    assert isinstance(adapters["claude"], ClaudeExecutionAdapter)
    assert isinstance(adapters["codex"], CodexExecutionAdapter)
    assert isinstance(adapters["opencode"], OpencodeExecutionAdapter)
    assert isinstance(adapters["qwen"], QwenExecutionAdapter)
    assert isinstance(adapters["kilo"], KiloExecutionAdapter)


def test_registry_require_raises_for_unknown_engine() -> None:
    registry = EngineAdapterRegistry()
    with pytest.raises(KeyError):
        registry.require("unknown-engine")


def test_opencode_adapter_builds_start_and_parses_stream(monkeypatch) -> None:
    registry = EngineAdapterRegistry()
    adapter = registry.require("opencode")
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/opencode"))

    command = adapter.build_start_command(
        prompt="hello",
        options={"model": "openai/gpt-5"},
    )
    assert command == [
        str(Path("/usr/bin/opencode")),
        "run",
        "--format",
        "json",
        "--model",
        "openai/gpt-5",
        "hello",
    ]

    parsed = adapter.parse_runtime_stream(
        stdout_raw=b'{"type":"text","part":{"text":"hello from opencode"}}\n',
        stderr_raw=b"",
    )

    assert parsed["parser"] == "opencode_ndjson"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from opencode"


def test_kilo_adapter_builds_start_and_parses_stream(monkeypatch) -> None:
    registry = EngineAdapterRegistry()
    adapter = registry.require("kilo")
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/kilo"))

    command = adapter.build_start_command(
        prompt="hello",
        options={"runtime_model": "kilo/kilo-auto/free"},
    )
    assert command == [
        str(Path("/usr/bin/kilo")),
        "run",
        "--format",
        "json",
        "--auto",
        "--model",
        "kilo/kilo-auto/free",
        "hello",
    ]

    parsed = adapter.parse_runtime_stream(
        stdout_raw=b'{"type":"text","sessionID":"s1","part":{"type":"text","text":"hello from kilo"}}\n',
        stderr_raw=b"",
    )

    assert parsed["parser"] == "kilo_jsonl"
    assert parsed["session_id"] == "s1"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from kilo"
