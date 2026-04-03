from __future__ import annotations

from typing import Any, Callable

from ....common.callbacks.server_base import LocalOAuthCallbackServer


class ClaudeLocalCallbackServer(LocalOAuthCallbackServer):
    def __init__(
        self,
        callback_handler: Callable[..., dict[str, Any]] | None = None,
        host: str = "127.0.0.1",
        port: int = 51123,
    ) -> None:
        super().__init__(
            callback_handler=callback_handler,
            host=host,
            port=port,
            callback_path="/callback",
            listener_name="Claude",
        )


claude_local_callback_server = ClaudeLocalCallbackServer()
