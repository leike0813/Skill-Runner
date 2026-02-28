from __future__ import annotations

from pathlib import Path
from typing import Dict

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import validate_adapter_profiles


class EngineAdapterRegistry:
    def __init__(self) -> None:
        validate_adapter_profiles(
            {
                "codex": Path(__file__).resolve().parents[2]
                / "engines"
                / "codex"
                / "adapter"
                / "adapter_profile.json",
                "gemini": Path(__file__).resolve().parents[2]
                / "engines"
                / "gemini"
                / "adapter"
                / "adapter_profile.json",
                "iflow": Path(__file__).resolve().parents[2]
                / "engines"
                / "iflow"
                / "adapter"
                / "adapter_profile.json",
                "opencode": Path(__file__).resolve().parents[2]
                / "engines"
                / "opencode"
                / "adapter"
                / "adapter_profile.json",
            }
        )
        self._adapters: Dict[str, EngineExecutionAdapter] = {
            "codex": CodexExecutionAdapter(),
            "gemini": GeminiExecutionAdapter(),
            "iflow": IFlowExecutionAdapter(),
            "opencode": OpencodeExecutionAdapter(),
        }

    def get(self, engine: str) -> EngineExecutionAdapter | None:
        return self._adapters.get(engine)

    def require(self, engine: str) -> EngineExecutionAdapter:
        adapter = self.get(engine)
        if adapter is None:
            raise KeyError(engine)
        return adapter

    def adapter_map(self) -> Dict[str, EngineExecutionAdapter]:
        return dict(self._adapters)


engine_adapter_registry = EngineAdapterRegistry()
