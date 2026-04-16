from __future__ import annotations

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


def test_engine_execution_adapter_component_wiring() -> None:
    claude = ClaudeExecutionAdapter()
    codex = CodexExecutionAdapter()
    gemini = GeminiExecutionAdapter()
    opencode = OpencodeExecutionAdapter()
    qwen = QwenExecutionAdapter()

    assert isinstance(claude, EngineExecutionAdapter)
    assert isinstance(codex, EngineExecutionAdapter)
    assert isinstance(gemini, EngineExecutionAdapter)
    assert isinstance(opencode, EngineExecutionAdapter)
    assert isinstance(qwen, EngineExecutionAdapter)
