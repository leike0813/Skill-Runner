from __future__ import annotations

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


def test_engine_execution_adapter_component_wiring() -> None:
    codex = CodexExecutionAdapter()
    gemini = GeminiExecutionAdapter()
    iflow = IFlowExecutionAdapter()
    opencode = OpencodeExecutionAdapter()

    assert isinstance(codex, EngineExecutionAdapter)
    assert isinstance(gemini, EngineExecutionAdapter)
    assert isinstance(iflow, EngineExecutionAdapter)
    assert isinstance(opencode, EngineExecutionAdapter)
