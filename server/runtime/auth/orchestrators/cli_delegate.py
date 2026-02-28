from __future__ import annotations

from typing import Any, Optional, Protocol


class _LegacyManagerProtocol(Protocol):
    def start_session(
        self,
        *,
        engine: str,
        method: str = "auth",
        auth_method: str | None = None,
        provider_id: str | None = None,
        transport: str | None = None,
        callback_base_url: str | None = None,
    ) -> dict[str, Any]:
        ...

    def get_session(self, session_id: str) -> dict[str, Any]:
        ...

    def input_session(self, session_id: str, kind: str, value: str) -> dict[str, Any]:
        ...

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        ...

    def resolve_transport_start_method(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: str | None = None,
    ) -> str:
        ...


class CliDelegateOrchestrator:
    """Transport-specific facade for cli_delegate sessions."""

    transport = "cli_delegate"
    state_machine = "cli_delegate_v1"

    def __init__(self, manager: _LegacyManagerProtocol) -> None:
        self._manager = manager

    def _resolve_method(
        self,
        *,
        engine: str,
        auth_method: str,
        provider_id: Optional[str],
    ) -> str:
        return self._manager.resolve_transport_start_method(
            transport=self.transport,
            engine=engine,
            auth_method=auth_method,
            provider_id=provider_id,
        )

    def start_session(
        self,
        *,
        engine: str,
        auth_method: str,
        provider_id: Optional[str],
        callback_base_url: Optional[str],
    ) -> dict[str, Any]:
        payload = self._manager.start_session(
            engine=engine,
            method=self._resolve_method(
                engine=engine,
                auth_method=auth_method,
                provider_id=provider_id,
            ),
            auth_method=auth_method,
            provider_id=provider_id,
            transport=self.transport,
            callback_base_url=callback_base_url,
        )
        payload["transport_state_machine"] = self.state_machine
        payload["orchestrator"] = "cli_delegate_orchestrator"
        return payload

    def get_session(self, session_id: str) -> dict[str, Any]:
        payload = self._manager.get_session(session_id)
        if str(payload.get("transport")) != self.transport:
            raise KeyError(session_id)
        payload["transport_state_machine"] = self.state_machine
        payload["orchestrator"] = "cli_delegate_orchestrator"
        return payload

    def input_session(self, session_id: str, kind: str, value: str) -> dict[str, Any]:
        payload = self._manager.input_session(session_id, kind, value)
        if str(payload.get("transport")) != self.transport:
            raise KeyError(session_id)
        payload["transport_state_machine"] = self.state_machine
        payload["orchestrator"] = "cli_delegate_orchestrator"
        return payload

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        payload = self._manager.cancel_session(session_id)
        if str(payload.get("transport")) != self.transport:
            raise KeyError(session_id)
        payload["transport_state_machine"] = self.state_machine
        payload["orchestrator"] = "cli_delegate_orchestrator"
        return payload

__all__ = ["CliDelegateOrchestrator"]
