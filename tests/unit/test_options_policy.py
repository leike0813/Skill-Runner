import pytest

from server.services.options_policy import OptionsPolicy


def test_unknown_runtime_options_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"unknown": 1})


def test_runtime_no_cache_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"no_cache": True})
    assert runtime_opts == {
        "no_cache": True,
        "execution_mode": "auto",
        "session_timeout_sec": 1200,
    }


def test_runtime_debug_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"debug": True})
    assert runtime_opts == {
        "debug": True,
        "execution_mode": "auto",
        "session_timeout_sec": 1200,
    }


def test_runtime_debug_keep_temp_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"debug_keep_temp": True})
    assert runtime_opts == {
        "debug_keep_temp": True,
        "execution_mode": "auto",
        "session_timeout_sec": 1200,
    }


def test_runtime_execution_mode_interactive_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"execution_mode": "interactive"})
    assert runtime_opts == {
        "execution_mode": "interactive",
        "interactive_require_user_reply": True,
        "session_timeout_sec": 1200,
    }


def test_runtime_interactive_require_user_reply_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options(
        {
            "execution_mode": "interactive",
            "interactive_require_user_reply": False,
        }
    )
    assert runtime_opts["interactive_require_user_reply"] is False


def test_runtime_execution_mode_invalid_rejected():
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError,
        match="runtime_options.execution_mode must be one of: auto, interactive",
    ):
        policy.validate_runtime_options({"execution_mode": "invalid"})


def test_session_timeout_override_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"session_timeout_sec": 321})
    assert runtime_opts["session_timeout_sec"] == 321


def test_legacy_session_timeout_mapping_supported():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"interactive_wait_timeout_sec": 456})
    assert runtime_opts["session_timeout_sec"] == 456
    assert "interactive_wait_timeout_sec" not in runtime_opts


def test_session_timeout_prefers_new_key_over_legacy():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options(
        {"session_timeout_sec": 222, "hard_wait_timeout_sec": 999}
    )
    assert runtime_opts["session_timeout_sec"] == 222
    assert "hard_wait_timeout_sec" not in runtime_opts


def test_session_timeout_must_be_positive_integer():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="session_timeout_sec must be a positive integer"):
        policy.validate_runtime_options({"session_timeout_sec": 0})


def test_interactive_require_user_reply_must_be_boolean():
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError, match="interactive_require_user_reply must be a boolean"
    ):
        policy.validate_runtime_options(
            {
                "execution_mode": "interactive",
                "interactive_require_user_reply": "yes",
            }
        )
