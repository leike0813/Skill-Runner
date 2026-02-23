from __future__ import annotations

import pytest

from server.adapters.codex_adapter import CodexAdapter
from server.adapters.gemini_adapter import GeminiAdapter
from server.adapters.iflow_adapter import IFlowAdapter
from server.adapters.opencode_adapter import OpencodeAdapter
from server.services.engine_adapter_registry import EngineAdapterRegistry


def test_registry_exposes_all_supported_adapters() -> None:
    registry = EngineAdapterRegistry()
    adapters = registry.adapter_map()

    assert set(adapters.keys()) == {"codex", "gemini", "iflow", "opencode"}
    assert isinstance(adapters["codex"], CodexAdapter)
    assert isinstance(adapters["gemini"], GeminiAdapter)
    assert isinstance(adapters["iflow"], IFlowAdapter)
    assert isinstance(adapters["opencode"], OpencodeAdapter)


def test_registry_require_raises_for_unknown_engine() -> None:
    registry = EngineAdapterRegistry()
    with pytest.raises(KeyError):
        registry.require("unknown-engine")


def test_opencode_adapter_is_capability_gated_but_parser_available() -> None:
    registry = EngineAdapterRegistry()
    adapter = registry.require("opencode")

    with pytest.raises(RuntimeError, match="ENGINE_CAPABILITY_UNAVAILABLE"):
        adapter.build_start_command(prompt="hello", options={})

    parsed = adapter.parse_runtime_stream(
        stdout_raw=b'{"type":"text","part":{"text":"hello from opencode"}}\n',
        stderr_raw=b"",
    )

    assert parsed["parser"] == "opencode_ndjson"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from opencode"
