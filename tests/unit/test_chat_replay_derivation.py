from server.runtime.chat_replay.factories import derive_chat_replay_rows_from_fcmp


def test_interaction_reply_accepted_derives_user_bubble() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 7,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:00:00Z",
            "type": "interaction.reply.accepted",
            "data": {
                "interaction_id": 3,
                "accepted_at": "2026-03-04T10:00:00Z",
                "response_preview": "男，38，程序员",
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["kind"] == "interaction_reply"
    assert rows[0]["text"] == "男，38，程序员"


def test_auth_input_accepted_derives_user_submission_bubble() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 8,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:01:00Z",
            "type": "auth.input.accepted",
            "data": {
                "auth_session_id": "auth-1",
                "submission_kind": "api_key",
                "accepted_at": "2026-03-04T10:01:00Z",
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["kind"] == "auth_submission"
    assert rows[0]["text"] == "API key submitted"


def test_terminal_state_changed_derives_system_bubble() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 9,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:02:00Z",
            "type": "conversation.state.changed",
            "data": {
                "from": "running",
                "to": "failed",
                "trigger": "turn.failed",
                "terminal": {
                    "status": "failed",
                    "error": {"message": "boom"},
                },
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["role"] == "system"
    assert rows[0]["kind"] == "orchestration_notice"
    assert rows[0]["text"] == "任务失败：boom"


def test_assistant_final_derivation_strips_ask_user_yaml_block() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 10,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:03:00Z",
            "type": "assistant.message.final",
            "data": {
                "message_id": "m-10",
                "text": (
                    "请补充信息。\n\n"
                    "<ASK_USER_YAML>\n"
                    "ask_user:\n"
                    "  kind: open_text\n"
                    "  ui_hints:\n"
                    "    hint: 请输入详细信息\n"
                    "</ASK_USER_YAML>"
                ),
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["role"] == "assistant"
    assert rows[0]["kind"] == "assistant_final"
    assert rows[0]["text"] == "请补充信息。"
