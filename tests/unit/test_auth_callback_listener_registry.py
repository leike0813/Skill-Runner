from server.runtime.auth.callbacks import CallbackListenerRegistry


class _FakeListener:
    def __init__(self) -> None:
        self.handler = None
        self.started = False
        self.stopped = False
        self._endpoint = "http://127.0.0.1:9999/callback"

    def set_callback_handler(self, callback_handler):  # noqa: ANN001
        self.handler = callback_handler

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.stopped = True

    @property
    def endpoint(self) -> str:
        return self._endpoint


def test_callback_listener_registry_start_and_stop():
    registry = CallbackListenerRegistry()
    listener = _FakeListener()
    registry.register(channel="openai", listener=listener)

    result = registry.start(channel="openai", callback_handler=lambda **_: {"status": "succeeded"})
    assert result.started is True
    assert result.endpoint == "http://127.0.0.1:9999/callback"
    assert listener.started is True
    assert listener.handler is not None

    registry.stop(channel="openai")
    assert listener.stopped is True


def test_callback_listener_registry_unknown_channel():
    registry = CallbackListenerRegistry()
    try:
        registry.start(channel="unknown", callback_handler=lambda **_: {"status": "failed"})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "not registered" in str(exc)
