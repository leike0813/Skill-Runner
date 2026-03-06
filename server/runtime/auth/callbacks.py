from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import html
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
            content = self._render_page_html(
                heading_key="success_heading",
                heading_fallback="OAuth authorization successful",
                message_key="success_message",
                message_fallback="You can close this page and return to Skill Runner.",
                detail_text="",
                error=False,
            )
            return HTMLResponse(
                status_code=status.HTTP_200_OK,
                content=content,
            )
        message = str(payload.get("error") or "unknown error")
        return HTMLResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=self._render_page_html(
                heading_key="error_heading",
                heading_fallback="OAuth callback failed",
                message_key="error_message",
                message_fallback="The callback returned an error. Please retry authorization.",
                detail_text=message,
                error=True,
            ),
        )

    def render_error(self, message: str, *, http_status: int) -> HTMLResponse:
        return HTMLResponse(
            status_code=http_status,
            content=self._render_page_html(
                heading_key="error_heading",
                heading_fallback="OAuth callback failed",
                message_key="error_message",
                message_fallback="The callback returned an error. Please retry authorization.",
                detail_text=message,
                error=True,
            ),
        )

    @staticmethod
    def _render_page_html(
        *,
        heading_key: str,
        heading_fallback: str,
        message_key: str,
        message_fallback: str,
        detail_text: str,
        error: bool,
    ) -> str:
        safe_detail = html.escape((detail_text or "").strip())
        tone_class = "callback-error" if error else "callback-success"
        detail_block = (
            f'<pre id="callback-detail" class="callback-detail">{safe_detail}</pre>'
            if safe_detail
            else ""
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(heading_fallback)}</title>
  <style>
    body {{
      margin: 0;
      font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
      background: #f3f7f5;
      color: #0f172a;
      display: grid;
      min-height: 100vh;
      place-items: center;
      padding: 20px;
    }}
    .callback-card {{
      width: min(560px, 100%);
      border-radius: 14px;
      border: 1px solid #d6e7de;
      background: #ffffff;
      box-shadow: 0 12px 36px rgba(15, 23, 42, 0.10);
      padding: 22px;
    }}
    .callback-title {{
      margin: 0;
      font-size: 20px;
      line-height: 1.3;
    }}
    .callback-success {{
      color: #166534;
    }}
    .callback-error {{
      color: #b91c1c;
    }}
    .callback-message {{
      margin-top: 10px;
      color: #334155;
      line-height: 1.6;
      font-size: 14px;
    }}
    .callback-detail {{
      margin: 12px 0 0;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid #e2e8f0;
      background: #f8fafc;
      color: #0f172a;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
  </style>
</head>
<body>
  <main class="callback-card">
    <h1 id="callback-title" class="callback-title {tone_class}">{html.escape(heading_fallback)}</h1>
    <p id="callback-message" class="callback-message">{html.escape(message_fallback)}</p>
    {detail_block}
  </main>
  <script>
    (() => {{
      const locale = (navigator.language || "en").toLowerCase();
      const language = locale.startsWith("zh")
        ? "zh"
        : locale.startsWith("fr")
          ? "fr"
          : locale.startsWith("ja")
            ? "ja"
            : "en";
      const dict = {{
        en: {{
          success_heading: "OAuth authorization successful",
          success_message: "You can close this page and return to Skill Runner.",
          error_heading: "OAuth callback failed",
          error_message: "The callback returned an error. Please retry authorization."
        }},
        zh: {{
          success_heading: "OAuth 授权成功",
          success_message: "你可以关闭当前页面并返回 Skill Runner。",
          error_heading: "OAuth 回调失败",
          error_message: "回调返回错误，请重新发起授权。"
        }},
        fr: {{
          success_heading: "Autorisation OAuth réussie",
          success_message: "Vous pouvez fermer cette page et retourner à Skill Runner.",
          error_heading: "Échec du rappel OAuth",
          error_message: "Le rappel OAuth a échoué. Veuillez réessayer."
        }},
        ja: {{
          success_heading: "OAuth 認証に成功しました",
          success_message: "このページを閉じて Skill Runner に戻ってください。",
          error_heading: "OAuth コールバックに失敗しました",
          error_message: "コールバックでエラーが返されました。再試行してください。"
        }}
      }};
      const messages = dict[language] || dict.en;
      const titleEl = document.getElementById("callback-title");
      const messageEl = document.getElementById("callback-message");
      if (titleEl) {{
        titleEl.textContent = messages[{heading_key!r}] || {heading_fallback!r};
      }}
      if (messageEl) {{
        messageEl.textContent = messages[{message_key!r}] || {message_fallback!r};
      }}
    }})();
  </script>
</body>
</html>"""


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
