from __future__ import annotations

from server.runtime.protocol.contracts import RuntimeParserResolverPort
from server.runtime.protocol.event_protocol import configure_runtime_parser_resolver
from server.services.orchestration.engine_adapter_registry import engine_adapter_registry


class _OrchestrationParserResolver(RuntimeParserResolverPort):
    def resolve(self, engine: str):
        return engine_adapter_registry.get(engine)


runtime_parser_resolver = _OrchestrationParserResolver()


def install_runtime_protocol_ports() -> None:
    configure_runtime_parser_resolver(runtime_parser_resolver)
