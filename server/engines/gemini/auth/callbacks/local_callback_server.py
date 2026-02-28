from __future__ import annotations

from typing import Any, Callable

from ....common.callbacks.server_base import LocalOAuthCallbackServer


class GeminiLocalCallbackServer(LocalOAuthCallbackServer):
    def __init__(
        self,
        callback_handler: Callable[..., dict[str, Any]] | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        super().__init__(
            callback_handler=callback_handler,
            host=host,
            port=port,
            callback_path="/oauth2callback",
            listener_name="Gemini",
        )


gemini_local_callback_server = GeminiLocalCallbackServer()
