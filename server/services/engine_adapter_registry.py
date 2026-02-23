from __future__ import annotations

from typing import Dict

from ..adapters.base import EngineAdapter
from ..adapters.codex_adapter import CodexAdapter
from ..adapters.gemini_adapter import GeminiAdapter
from ..adapters.iflow_adapter import IFlowAdapter
from ..adapters.opencode_adapter import OpencodeAdapter


class EngineAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, EngineAdapter] = {
            "codex": CodexAdapter(),
            "gemini": GeminiAdapter(),
            "iflow": IFlowAdapter(),
            "opencode": OpencodeAdapter(),
        }

    def get(self, engine: str) -> EngineAdapter | None:
        return self._adapters.get(engine)

    def require(self, engine: str) -> EngineAdapter:
        adapter = self.get(engine)
        if adapter is None:
            raise KeyError(engine)
        return adapter

    def adapter_map(self) -> Dict[str, EngineAdapter]:
        return dict(self._adapters)


engine_adapter_registry = EngineAdapterRegistry()
