import urllib.error
import urllib.request

from server.engines.opencode.auth.callbacks.antigravity_local_callback_server import (
    AntigravityLocalCallbackServer,
)


def test_antigravity_local_callback_server_success():
    captured = {}

    def _callback_handler(*, state, code=None, error=None):  # noqa: ANN001
        captured["state"] = state
        captured["code"] = code
        captured["error"] = error
        return {"status": "succeeded", "error": None}

    server = AntigravityLocalCallbackServer(callback_handler=_callback_handler, host="127.0.0.1", port=0)
    try:
        assert server.start() is True
        with urllib.request.urlopen(f"{server.endpoint}?state=s1&code=c1", timeout=2.0) as resp:
            body = resp.read().decode("utf-8")
            assert resp.status == 200
        assert "OAuth authorization successful" in body
        assert captured == {"state": "s1", "code": "c1", "error": None}
    finally:
        server.stop()


def test_antigravity_local_callback_server_missing_state():
    server = AntigravityLocalCallbackServer(
        callback_handler=lambda **_: {"status": "succeeded", "error": None},
        host="127.0.0.1",
        port=0,
    )
    try:
        assert server.start() is True
        try:
            urllib.request.urlopen(server.endpoint, timeout=2.0)
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            body = exc.read().decode("utf-8")
            assert "Missing state" in body
    finally:
        server.stop()
