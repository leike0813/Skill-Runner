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


def test_runtime_debug_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"debug": True})


def test_runtime_debug_keep_temp_rejected():
    policy = OptionsPolicy()
    with pytest.raises(ValueError, match="Unknown runtime_options"):
        policy.validate_runtime_options({"debug_keep_temp": True})


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


def test_interactive_reply_timeout_zero_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"interactive_reply_timeout_sec": 0})
    assert runtime_opts["interactive_reply_timeout_sec"] == 0


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


def test_hard_timeout_seconds_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"hard_timeout_seconds": 45})
    assert runtime_opts["hard_timeout_seconds"] == 45


@pytest.mark.parametrize("value", [0, -1, "bad", None])
def test_hard_timeout_seconds_must_be_positive_integer(value):
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError, match="runtime_options.hard_timeout_seconds must be a positive integer"
    ):
        policy.validate_runtime_options({"hard_timeout_seconds": value})


def test_runtime_env_allowed_and_preserved_as_local_option():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"env": {"FOO": "bar", "_X": ""}})
    assert runtime_opts["env"] == {"FOO": "bar", "_X": ""}


def test_collect_skill_run_feedback_boolean_allowed_and_preserved():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"collect_skill_run_feedback": True})
    assert runtime_opts["collect_skill_run_feedback"] is True


@pytest.mark.parametrize("value", ["true", 1, 0, None])
def test_collect_skill_run_feedback_must_be_boolean(value):
    policy = OptionsPolicy()
    with pytest.raises(
        ValueError,
        match="runtime_options.collect_skill_run_feedback must be a boolean",
    ):
        policy.validate_runtime_options({"collect_skill_run_feedback": value})


def test_runtime_env_redacted_projection_allowed_for_persisted_options():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options({"env": {"FOO": {"redacted": True}}})
    assert runtime_opts["env"] == {"FOO": {"redacted": True}}


def test_workspace_file_bindings_shape_allowed():
    policy = OptionsPolicy()
    runtime_opts = policy.validate_runtime_options(
        {
            "workspace": {
                "mode": "reuse",
                "request_id": "req-a",
                "file_bindings": [
                    {
                        "input_key": "artifact_file",
                        "source_request_id": "req-a",
                        "source_path": "runtime/artifact.json",
                        "target_path": "inputs/artifact_file/artifact.json",
                    }
                ],
            }
        }
    )
    assert runtime_opts["workspace"]["file_bindings"][0]["input_key"] == "artifact_file"


@pytest.mark.parametrize(
    "workspace",
    [
        {"mode": "reuse", "request_id": "req-a", "file_bindings": "bad"},
        {"mode": "reuse", "request_id": "req-a", "file_bindings": ["bad"]},
        {
            "mode": "reuse",
            "request_id": "req-a",
            "file_bindings": [
                {
                    "input_key": "artifact_file",
                    "source_request_id": "req-a",
                    "source_path": "runtime/artifact.json",
                }
            ],
        },
    ],
)
def test_workspace_file_bindings_invalid_shape_rejected(workspace):
    policy = OptionsPolicy()
    with pytest.raises(ValueError):
        policy.validate_runtime_options({"workspace": workspace})


@pytest.mark.parametrize(
    "env",
    [
        "bad",
        {"lower": "value"},
        {"1BAD": "value"},
        {"PATH": "value"},
        {"PYTHONPATH": "value"},
        {"FOO": 123},
        {"FOO": "x" * 8193},
        {f"FOO_{idx}": "x" for idx in range(65)},
    ],
)
def test_runtime_env_invalid_values_rejected(env):
    policy = OptionsPolicy()
    with pytest.raises(ValueError):
        policy.validate_runtime_options({"env": env})
