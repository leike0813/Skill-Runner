from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SessionPointer:
    session_id: str
    transport: str
    engine: str
    auth_method: str
    provider_id: Optional[str]


class AuthSessionStore:
    """Minimal index for transport-specific session routing."""

    def __init__(self) -> None:
        self._by_id: Dict[str, SessionPointer] = {}
        self._active_by_transport: Dict[str, str] = {}

    def upsert(self, pointer: SessionPointer) -> None:
        self._by_id[pointer.session_id] = pointer
        self._active_by_transport[pointer.transport] = pointer.session_id

    def get(self, session_id: str) -> SessionPointer:
        pointer = self._by_id.get(session_id)
        if pointer is None:
            raise KeyError(session_id)
        return pointer

    def get_active(self, transport: str) -> Optional[SessionPointer]:
        sid = self._active_by_transport.get(transport)
        if not sid:
            return None
        return self._by_id.get(sid)

    def clear_active(self, transport: str, session_id: str) -> None:
        if self._active_by_transport.get(transport) == session_id:
            self._active_by_transport.pop(transport, None)

    def remove(self, session_id: str) -> None:
        pointer = self._by_id.pop(session_id, None)
        if pointer is None:
            return
        if self._active_by_transport.get(pointer.transport) == session_id:
            self._active_by_transport.pop(pointer.transport, None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessions": {
                sid: {
                    "session_id": ptr.session_id,
                    "transport": ptr.transport,
                    "engine": ptr.engine,
                    "auth_method": ptr.auth_method,
                    "provider_id": ptr.provider_id,
                }
                for sid, ptr in self._by_id.items()
            },
            "active_by_transport": dict(self._active_by_transport),
        }
