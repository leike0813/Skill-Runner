from __future__ import annotations

from typing import Any, Callable

from .server_base import LocalOAuthCallbackServer


class OpenAILocalCallbackServer(LocalOAuthCallbackServer):
    def __init__(
        self,
        callback_handler: Callable[..., dict[str, Any]] | None = None,
        host: str = "127.0.0.1",
        port: int = 1455,
    ) -> None:
        super().__init__(
            callback_handler=callback_handler,
            host=host,
            port=port,
            callback_path="/auth/callback",
            listener_name="OpenAI",
        )


openai_local_callback_server = OpenAILocalCallbackServer()

