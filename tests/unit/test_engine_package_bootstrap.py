from __future__ import annotations

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.engines.opencode.auth import opencode_auth_provider_registry


def test_engine_package_execution_adapters() -> None:
    assert isinstance(CodexExecutionAdapter(), CodexExecutionAdapter)
    assert isinstance(GeminiExecutionAdapter(), GeminiExecutionAdapter)
    assert isinstance(IFlowExecutionAdapter(), IFlowExecutionAdapter)
    assert isinstance(OpencodeExecutionAdapter(), OpencodeExecutionAdapter)


def test_opencode_auth_registry_reexport_is_available() -> None:
    provider = opencode_auth_provider_registry.get("openai")
    assert provider.provider_id == "openai"
