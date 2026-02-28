from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import status  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]


@dataclass(frozen=True)
class CallbackStateRef:
    channel: str
    state: str
    session_id: str


class CallbackStateStore:
    """Channel-scoped one-shot callback state registry."""

    def __init__(self) -> None:
        self._state_index: dict[tuple[str, str], str] = {}
        self._consumed: set[tuple[str, str]] = set()

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        value = channel.strip().lower()
        if not value:
            raise ValueError("OAuth callback channel is required")
        return value

    @staticmethod
    def _normalize_state(state: str) -> str:
        value = state.strip()
        if not value:
            raise ValueError("OAuth callback state is required")
        return value

    def register(self, *, channel: str, state: str, session_id: str) -> CallbackStateRef:
        normalized_channel = self._normalize_channel(channel)
        normalized_state = self._normalize_state(state)
        key = (normalized_channel, normalized_state)
        self._state_index[key] = session_id
        self._consumed.discard(key)
        return CallbackStateRef(
            channel=normalized_channel,
            state=normalized_state,
            session_id=session_id,
        )

    def unregister(self, *, channel: str, state: str) -> None:
        normalized_channel = self._normalize_channel(channel)
        normalized_state = self._normalize_state(state)
        key = (normalized_channel, normalized_state)
        self._state_index.pop(key, None)

    def is_consumed(self, *, channel: str, state: str) -> bool:
        normalized_channel = self._normalize_channel(channel)
        normalized_state = self._normalize_state(state)
        return (normalized_channel, normalized_state) in self._consumed

    def resolve_session_id(self, *, channel: str, state: str) -> str | None:
        normalized_channel = self._normalize_channel(channel)
        normalized_state = self._normalize_state(state)
        return self._state_index.get((normalized_channel, normalized_state))

    def consume(self, *, channel: str, state: str) -> None:
        normalized_channel = self._normalize_channel(channel)
        normalized_state = self._normalize_state(state)
        key = (normalized_channel, normalized_state)
        self._state_index.pop(key, None)
        self._consumed.add(key)


@dataclass(frozen=True)
class CallbackPayload:
    state: str
    code: str | None
    error: str | None


class OAuthCallbackRouter:
    """Normalize OAuth callback handling and HTML response rendering."""

    def parse(
        self,
        *,
        state: str | None = None,
        code: str | None = None,
        error: str | None = None,
    ) -> CallbackPayload:
        normalized_state = (state or "").strip()
        if not normalized_state:
            raise ValueError("Missing state.")
        normalized_code = (code or "").strip() or None
        normalized_error = (error or "").strip() or None
        return CallbackPayload(
            state=normalized_state,
            code=normalized_code,
            error=normalized_error,
        )

    def execute(
        self,
        payload: CallbackPayload,
        complete_fn: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        return complete_fn(
            state=payload.state,
            code=payload.code,
            error=payload.error,
        )

    def render(self, payload: dict[str, Any]) -> HTMLResponse:
        if str(payload.get("status")) == "succeeded":
            return HTMLResponse(
                status_code=status.HTTP_200_OK,
                content=(
                    "<html><body><h3>OAuth authorization successful</h3>"
                    "<p>You can close this page and return to Skill Runner.</p></body></html>"
                ),
            )
        return HTMLResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=(
                "<html><body><h3>OAuth callback failed</h3>"
                f"<p>{str(payload.get('error') or 'unknown error')}</p></body></html>"
            ),
        )

    def render_error(self, message: str, *, http_status: int) -> HTMLResponse:
        return HTMLResponse(
            status_code=http_status,
            content=f"<html><body><h3>OAuth callback failed</h3><p>{message}</p></body></html>",
        )


class CallbackListener(Protocol):
    def set_callback_handler(self, callback_handler: Callable[..., dict[str, Any]]) -> None:
        ...

    def start(self) -> bool:
        ...

    def stop(self) -> None:
        ...

    @property
    def endpoint(self) -> str:
        ...


@dataclass(frozen=True)
class CallbackListenerStartResult:
    started: bool
    endpoint: str | None


class CallbackListenerRegistry:
    def __init__(self) -> None:
        self._listeners: dict[str, CallbackListener] = {}

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        value = channel.strip().lower()
        if not value:
            raise ValueError("OAuth callback channel is required")
        return value

    def register(self, *, channel: str, listener: CallbackListener) -> None:
        normalized_channel = self._normalize_channel(channel)
        self._listeners[normalized_channel] = listener

    def start(
        self,
        *,
        channel: str,
        callback_handler: Callable[..., dict[str, Any]],
    ) -> CallbackListenerStartResult:
        listener = self._listeners.get(self._normalize_channel(channel))
        if listener is None:
            raise ValueError(f"Callback listener channel not registered: {channel}")
        listener.set_callback_handler(callback_handler)
        started = bool(listener.start())
        endpoint = listener.endpoint if started else None
        return CallbackListenerStartResult(started=started, endpoint=endpoint)

    def stop(self, *, channel: str) -> None:
        listener = self._listeners.get(self._normalize_channel(channel))
        if listener is None:
            return
        listener.stop()


oauth_callback_router = OAuthCallbackRouter()

