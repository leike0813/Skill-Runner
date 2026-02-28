from __future__ import annotations

from pathlib import Path

import pytest

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.services.engine_adapter_registry import EngineAdapterRegistry


def test_registry_exposes_all_supported_adapters() -> None:
    registry = EngineAdapterRegistry()
    adapters = registry.adapter_map()

    assert set(adapters.keys()) == {"codex", "gemini", "iflow", "opencode"}
    assert isinstance(adapters["codex"], CodexExecutionAdapter)
    assert isinstance(adapters["gemini"], GeminiExecutionAdapter)
    assert isinstance(adapters["iflow"], IFlowExecutionAdapter)
    assert isinstance(adapters["opencode"], OpencodeExecutionAdapter)


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
        "/usr/bin/opencode",
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
