from server.services.orchestration.run_execution_core import (
    build_effective_runtime_options,
    normalize_effective_runtime_policy,
    resolve_conversation_mode,
)


def test_resolve_conversation_mode_defaults_to_session():
    assert resolve_conversation_mode(None) == "session"
    assert resolve_conversation_mode({}) == "session"


def test_non_session_dual_mode_defaults_to_auto():
    policy = normalize_effective_runtime_policy(
        declared_modes={"auto", "interactive"},
        runtime_options={"execution_mode": "interactive"},
        client_metadata={"conversation_mode": "non_session"},
    )
    assert policy.requested_execution_mode == "interactive"
    assert policy.effective_execution_mode == "auto"
    assert policy.conversation_mode == "non_session"
    assert policy.interactive_auto_reply is False
    assert policy.interactive_reply_timeout_sec == 0


def test_non_session_interactive_only_normalizes_to_zero_timeout_autoreply():
    policy = normalize_effective_runtime_policy(
        declared_modes={"interactive"},
        runtime_options={},
        client_metadata={"conversation_mode": "non_session"},
    )
    assert policy.requested_execution_mode == "auto"
    assert policy.effective_execution_mode == "interactive"
    assert policy.conversation_mode == "non_session"
    assert policy.interactive_auto_reply is True
    assert policy.interactive_reply_timeout_sec == 0

    effective = build_effective_runtime_options(
        runtime_options={"execution_mode": "auto"},
        policy=policy,
    )
    assert effective["execution_mode"] == "interactive"
    assert effective["interactive_auto_reply"] is True
    assert effective["interactive_reply_timeout_sec"] == 0


def test_session_interactive_preserves_requested_policy():
    policy = normalize_effective_runtime_policy(
        declared_modes={"auto", "interactive"},
        runtime_options={
            "execution_mode": "interactive",
            "interactive_auto_reply": True,
            "interactive_reply_timeout_sec": 8,
        },
        client_metadata={"conversation_mode": "session"},
    )
    assert policy.effective_execution_mode == "interactive"
    assert policy.conversation_mode == "session"
    assert policy.interactive_auto_reply is True
    assert policy.interactive_reply_timeout_sec == 8
