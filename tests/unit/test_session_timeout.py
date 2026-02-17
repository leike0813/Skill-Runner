from server.services.session_timeout import (
    DEFAULT_SESSION_TIMEOUT_SEC,
    resolve_session_timeout,
)


def test_resolve_session_timeout_default():
    resolution = resolve_session_timeout({})
    assert resolution.value == DEFAULT_SESSION_TIMEOUT_SEC
    assert resolution.source == "default"


def test_resolve_session_timeout_prefers_new_key():
    resolution = resolve_session_timeout({"session_timeout_sec": 300})
    assert resolution.value == 300
    assert resolution.source == "session_timeout_sec"


def test_resolve_session_timeout_maps_legacy_key():
    resolution = resolve_session_timeout({"interactive_wait_timeout_sec": 180})
    assert resolution.value == 180
    assert resolution.source == "legacy"
    assert resolution.deprecated_keys_used == ("interactive_wait_timeout_sec",)


def test_resolve_session_timeout_ignores_legacy_when_new_present():
    resolution = resolve_session_timeout(
        {
            "session_timeout_sec": 90,
            "interactive_wait_timeout_sec": 180,
            "hard_wait_timeout_sec": 300,
        }
    )
    assert resolution.value == 90
    assert resolution.source == "session_timeout_sec"
    assert set(resolution.legacy_keys_ignored) == {
        "interactive_wait_timeout_sec",
        "hard_wait_timeout_sec",
    }
