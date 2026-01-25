import pytest

from server.services.options_policy import OptionsPolicy


def test_unknown_runtime_options_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"unknown": 1})


def test_runtime_no_cache_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"no_cache": True})
    assert runtime_opts == {"no_cache": True}


def test_runtime_debug_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"debug": True})
    assert runtime_opts == {"debug": True}
