from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger(__name__)


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class LocalOAuthCallbackServer:
    def __init__(
        self,
        *,
        callback_handler: Callable[..., dict[str, Any]] | None = None,
        host: str,
        port: int,
        callback_path: str,
        listener_name: str,
    ) -> None:
        self._callback_handler = callback_handler
        self._host = host
        self._port = port
        self._bound_port = port
        self._callback_path = callback_path
        self._listener_name = listener_name
        self._server: _ReusableThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._lock = Lock()

    def set_callback_handler(self, callback_handler: Callable[..., dict[str, Any]]) -> None:
        with self._lock:
            self._callback_handler = callback_handler

    def start(self) -> bool:
        with self._lock:
            if self._server is not None:
                return True

            owner = self
            callback_path = self._callback_path
            listener_name = self._listener_name

            class CallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802
                    parsed = urlsplit(self.path)
                    if parsed.path != callback_path:
                        self._respond(
                            status=404,
                            title="OAuth callback not found",
                            message="Unsupported callback path.",
                        )
                        return
                    query = parse_qs(parsed.query)
                    state = (query.get("state", [""])[0] or "").strip()
                    code = (query.get("code", [""])[0] or "").strip()
                    error = (query.get("error", [""])[0] or "").strip()
                    if not state:
                        self._respond(
                            status=400,
                            title="OAuth callback failed",
                            message="Missing state.",
                        )
                        return
                    if owner._callback_handler is None:
                        self._respond(
                            status=503,
                            title="OAuth callback unavailable",
                            message="Callback handler is not configured.",
                        )
                        return
                    try:
                        payload = owner._callback_handler(
                            state=state,
                            code=code or None,
                            error=error or None,
                        )
                    except ValueError as exc:
                        self._respond(
                            status=400,
                            title="OAuth callback failed",
                            message=str(exc),
                        )
                        return
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.exception("%s local callback handling failed: %s", listener_name, exc)
                        self._respond(
                            status=500,
                            title="OAuth callback failed",
                            message=str(exc),
                        )
                        return

                    if str(payload.get("status")) == "succeeded":
                        self._respond(
                            status=200,
                            title="OAuth authorization successful",
                            message="You can close this page and return to Skill Runner.",
                        )
                        return
                    self._respond(
                        status=400,
                        title="OAuth callback failed",
                        message=str(payload.get("error") or "unknown error"),
                    )

                def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                    return

                def _respond(self, *, status: int, title: str, message: str) -> None:
                    body = (
                        "<html><body>"
                        f"<h3>{title}</h3>"
                        f"<p>{message}</p>"
                        "</body></html>"
                    )
                    encoded = body.encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)

            try:
                server = _ReusableThreadingHTTPServer((self._host, self._port), CallbackHandler)
            except OSError as exc:
                logger.warning(
                    "%s local callback server unavailable on %s:%s: %s",
                    listener_name,
                    self._host,
                    self._port,
                    exc,
                )
                self._server = None
                self._thread = None
                return False

            thread = Thread(target=server.serve_forever, daemon=True, name=f"{listener_name}-local-callback")
            thread.start()
            self._server = server
            self._thread = thread
            self._bound_port = int(server.server_port)
            logger.info(
                "%s local callback server started at http://%s:%s%s",
                listener_name,
                self._host,
                self._bound_port,
                callback_path,
            )
            return True

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
        if server is None:
            return
        try:
            server.shutdown()
            server.server_close()
        finally:
            if thread is not None:
                thread.join(timeout=1.0)

    @property
    def endpoint(self) -> str:
        return f"http://{self._host}:{self._bound_port}{self._callback_path}"

