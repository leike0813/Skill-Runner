from __future__ import annotations

from typing import Protocol

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


class RuntimeParserResolverPort(Protocol):
    def resolve(self, engine: str) -> EngineExecutionAdapter | None:
        ...
