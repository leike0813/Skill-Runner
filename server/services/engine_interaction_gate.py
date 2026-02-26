import threading
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EngineInteractionBusyError(RuntimeError):
    """Raised when another interactive engine session already owns the gate."""


class EngineInteractionGate:
    """
    Process-local gate to prevent concurrent interactive sessions that would
    contend for a single human operator (e.g. inline TUI vs auth flow).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: Dict[str, Any] | None = None

    def acquire(self, scope: str, session_id: str, engine: str) -> Dict[str, Any]:
        with self._lock:
            current = self._active
            if current is not None:
                if (
                    str(current.get("scope")) == scope
                    and str(current.get("session_id")) == session_id
                ):
                    return dict(current)
                raise EngineInteractionBusyError(
                    "Interactive gate busy: "
                    f"scope={current.get('scope')} engine={current.get('engine')} "
                    f"session_id={current.get('session_id')}"
                )
            payload = {
                "scope": scope,
                "session_id": session_id,
                "engine": engine,
                "created_at": _utc_iso(),
            }
            self._active = payload
            return dict(payload)

    def release(self, scope: str, session_id: str) -> None:
        with self._lock:
            current = self._active
            if current is None:
                return
            if (
                str(current.get("scope")) == scope
                and str(current.get("session_id")) == session_id
            ):
                self._active = None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if self._active is None:
                return {"active": False}
            payload = dict(self._active)
            payload["active"] = True
            return payload


engine_interaction_gate = EngineInteractionGate()
