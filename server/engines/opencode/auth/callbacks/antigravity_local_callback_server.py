from __future__ import annotations

from typing import Any, Callable

from ....common.callbacks.server_base import LocalOAuthCallbackServer


class AntigravityLocalCallbackServer(LocalOAuthCallbackServer):
    def __init__(
        self,
        callback_handler: Callable[..., dict[str, Any]] | None = None,
        host: str = "127.0.0.1",
        port: int = 51121,
    ) -> None:
        super().__init__(
            callback_handler=callback_handler,
            host=host,
            port=port,
            callback_path="/oauth-callback",
            listener_name="Antigravity",
        )


antigravity_local_callback_server = AntigravityLocalCallbackServer()
