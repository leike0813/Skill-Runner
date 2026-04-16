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
        self._active_by_key: Dict[str, Dict[str, Any]] = {}

    def _scope_key(self, scope: str, engine: str, provider_id: str | None = None) -> str:
        normalized_scope = scope.strip().lower()
        normalized_engine = engine.strip().lower()
        if normalized_scope == "auth_flow":
            normalized_provider = (provider_id or "_none_").strip().lower() or "_none_"
            return f"{normalized_scope}::{normalized_engine}::{normalized_provider}"
        return f"{normalized_scope}::{normalized_engine}"

    def acquire(self, scope: str, session_id: str, engine: str, provider_id: str | None = None) -> Dict[str, Any]:
        with self._lock:
            scope_key = self._scope_key(scope, engine, provider_id)
            requested_scope = scope.strip().lower()
            for current in self._active_by_key.values():
                current_scope = str(current.get("scope") or "").strip().lower()
                current_scope_key = str(current.get("scope_key") or "")
                if (
                    current_scope == requested_scope
                    and current_scope_key == scope_key
                    and str(current.get("session_id")) == session_id
                ):
                    return dict(current)
                if requested_scope == "auth_flow" and current_scope == "auth_flow":
                    if current_scope_key != scope_key:
                        continue
                raise EngineInteractionBusyError(
                    "Interactive gate busy: "
                    f"scope={current.get('scope')} engine={current.get('engine')} "
                    f"session_id={current.get('session_id')}"
                )
            payload = {
                "scope": scope,
                "scope_key": scope_key,
                "session_id": session_id,
                "engine": engine,
                "provider_id": provider_id,
                "created_at": _utc_iso(),
            }
            self._active_by_key[scope_key] = payload
            return dict(payload)

    def release(self, scope: str, session_id: str, engine: str | None = None, provider_id: str | None = None) -> None:
        with self._lock:
            if engine is not None:
                current = self._active_by_key.get(self._scope_key(scope, engine, provider_id))
                if current is None:
                    return
                if (
                    str(current.get("scope")) == scope
                    and str(current.get("session_id")) == session_id
                ):
                    self._active_by_key.pop(str(current.get("scope_key")), None)
                return
            for key, current in list(self._active_by_key.items()):
                if (
                    str(current.get("scope")) == scope
                    and str(current.get("session_id")) == session_id
                ):
                    self._active_by_key.pop(key, None)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_by_key:
                return {"active": False}
            _, current = next(iter(self._active_by_key.items()))
            payload = dict(current)
            payload["active"] = True
            return payload


engine_interaction_gate = EngineInteractionGate()
