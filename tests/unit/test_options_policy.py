import pytest

from server.services.platform.options_policy import OptionsPolicy


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
        "interactive_auto_reply": False,
        "interactive_reply_timeout_sec": 1200,
    }


def test_runtime_debug_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"debug": True})
    assert runtime_opts == {
        "debug": True,
        "execution_mode": "auto",
        "interactive_auto_reply": False,
        "interactive_reply_timeout_sec": 1200,
    }


def test_runtime_debug_keep_temp_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"debug_keep_temp": True})
    assert runtime_opts == {
        "debug_keep_temp": True,
        "execution_mode": "auto",
        "interactive_auto_reply": False,
        "interactive_reply_timeout_sec": 1200,
    }


def test_runtime_execution_mode_interactive_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"execution_mode": "interactive"})
    assert runtime_opts == {
        "execution_mode": "interactive",
        "interactive_auto_reply": False,
        "interactive_reply_timeout_sec": 1200,
    }


def test_runtime_interactive_auto_reply_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options(
        {
            "execution_mode": "interactive",
            "interactive_auto_reply": True,
        }
    )
    assert runtime_opts["interactive_auto_reply"] is True


def test_runtime_execution_mode_invalid_rejected():
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError,
        match="runtime_options.execution_mode must be one of: auto, interactive",
    ):
        policy.validate_runtime_options({"execution_mode": "invalid"})


def test_interactive_reply_timeout_override_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"interactive_reply_timeout_sec": 321})
    assert runtime_opts["interactive_reply_timeout_sec"] == 321


def test_legacy_timeout_key_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"session_timeout_sec": 456})


def test_legacy_interactive_policy_key_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"interactive_require_user_reply": False})


def test_interactive_reply_timeout_must_be_positive_integer():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="interactive_reply_timeout_sec must be a positive integer"):
        policy.validate_runtime_options({"interactive_reply_timeout_sec": 0})


def test_interactive_auto_reply_must_be_boolean():
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError, match="interactive_auto_reply must be a boolean"
    ):
        policy.validate_runtime_options(
            {
                "execution_mode": "interactive",
                "interactive_auto_reply": "yes",
            }
        )
