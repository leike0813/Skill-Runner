from server.runtime.session.timeout import (
    DEFAULT_SESSION_TIMEOUT_SEC,
    resolve_interactive_reply_timeout,
)


def test_resolve_interactive_reply_timeout_default():
    resolution = resolve_interactive_reply_timeout({})
    assert resolution.value == DEFAULT_SESSION_TIMEOUT_SEC
    assert resolution.source == "default"


def test_resolve_interactive_reply_timeout_prefers_new_key():
    resolution = resolve_interactive_reply_timeout({"interactive_reply_timeout_sec": 300})
    assert resolution.value == 300
    assert resolution.source == "interactive_reply_timeout_sec"
