from __future__ import annotations

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


def _assert_components(adapter: EngineExecutionAdapter) -> None:
    assert adapter.config_composer is not None
    assert adapter.workspace_provisioner is not None
    assert adapter.prompt_builder is not None
    assert adapter.command_builder is not None
    assert adapter.stream_parser is not None
    assert adapter.session_codec is not None


def test_engine_execution_adapters_build_directly() -> None:
    adapters = [
        CodexExecutionAdapter(),
        GeminiExecutionAdapter(),
        IFlowExecutionAdapter(),
        OpencodeExecutionAdapter(),
    ]
    for adapter in adapters:
        assert isinstance(adapter, EngineExecutionAdapter)
        _assert_components(adapter)
