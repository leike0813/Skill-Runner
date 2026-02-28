from server.runtime.auth.callbacks import CallbackStateStore


def test_callback_state_store_register_resolve_consume():
    store = CallbackStateStore()
    store.register(channel="openai", state="state-1", session_id="s-1")
    assert store.resolve_session_id(channel="openai", state="state-1") == "s-1"
    assert store.is_consumed(channel="openai", state="state-1") is False

    store.consume(channel="openai", state="state-1")
    assert store.resolve_session_id(channel="openai", state="state-1") is None
    assert store.is_consumed(channel="openai", state="state-1") is True


def test_callback_state_store_is_channel_scoped():
    store = CallbackStateStore()
    store.register(channel="openai", state="same", session_id="openai-1")
    store.register(channel="gemini", state="same", session_id="gemini-1")

    assert store.resolve_session_id(channel="openai", state="same") == "openai-1"
    assert store.resolve_session_id(channel="gemini", state="same") == "gemini-1"


def test_callback_state_store_unregister_keeps_consumed_marker():
    store = CallbackStateStore()
    store.register(channel="iflow", state="state-x", session_id="s-x")
    store.consume(channel="iflow", state="state-x")
    assert store.is_consumed(channel="iflow", state="state-x") is True

    store.unregister(channel="iflow", state="state-x")
    assert store.is_consumed(channel="iflow", state="state-x") is True
    assert store.resolve_session_id(channel="iflow", state="state-x") is None
