from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from server.runtime.adapter.types import LiveParserEmission

if TYPE_CHECKING:
    from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


class RuntimeParserResolverPort(Protocol):
    def resolve(self, engine: str) -> "EngineExecutionAdapter | None":
        ...


class LiveStreamParserSession(Protocol):
    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        ...

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        ...


class LiveRuntimeEmitter(Protocol):
    async def on_stream_chunk(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> None:
        ...

    async def on_process_exit(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> None:
        ...
