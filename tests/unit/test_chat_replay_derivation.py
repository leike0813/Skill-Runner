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


def test_assistant_final_derivation_keeps_raw_ref_in_correlation() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 11,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:03:30Z",
            "type": "assistant.message.final",
            "data": {
                "message_id": "m-11",
                "replaces_message_id": "m-10",
                "text": "最终答复",
            },
            "raw_ref": {
                "stream": "stdout",
                "byte_from": 10,
                "byte_to": 20,
                "attempt_number": 2,
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["correlation"]["raw_ref"]["stream"] == "stdout"
    assert rows[0]["correlation"]["raw_ref"]["byte_from"] == 10
    assert rows[0]["correlation"]["replaces_message_id"] == "m-10"


def test_assistant_final_derivation_prefers_display_text() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 12,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:04:00Z",
            "type": "assistant.message.final",
            "data": {
                "message_id": "m-12",
                "text": '{"__SKILL_DONE__":false,"message":"raw pending"}',
                "display_text": "Choose the next action.",
                "display_format": "plain_text",
                "display_origin": "pending_branch",
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["text"] == "Choose the next action."


def test_assistant_superseded_derivation_maps_to_revision_row() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 13,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:04:30Z",
            "type": "assistant.message.superseded",
            "data": {
                "message_id": "m-12",
                "message_family_id": "family-1",
                "reason": "output_repair_started",
                "repair_round_index": 1,
                "replacement_expected": True,
            },
            "meta": {"attempt": 2},
        }
    )

    assert len(rows) == 1
    assert rows[0]["role"] == "assistant"
    assert rows[0]["kind"] == "assistant_revision"
    assert rows[0]["text"] == ""
    assert rows[0]["correlation"]["message_id"] == "m-12"
    assert rows[0]["correlation"]["message_family_id"] == "family-1"


def test_assistant_process_derivation_maps_reasoning_tool_and_command() -> None:
    reasoning_rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 12,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:04:00Z",
            "type": "assistant.reasoning",
            "data": {
                "message_id": "m-12",
                "summary": "Inspecting input structure",
                "details": {"step": "inspect"},
            },
            "meta": {"attempt": 2},
        }
    )
    tool_rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 13,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:04:30Z",
            "type": "assistant.tool_call",
            "data": {
                "message_id": "m-13",
                "details": {
                    "tool_name": "search",
                    "args": "q=contract",
                },
            },
            "meta": {"attempt": 2},
        }
    )
    command_rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 14,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:05:00Z",
            "type": "assistant.command_execution",
            "data": {
                "message_id": "m-14",
                "details": {
                    "command": "python -m pytest -q tests/unit/test_chat_replay_derivation.py",
                },
            },
            "meta": {"attempt": 2},
        }
    )

    assert reasoning_rows[0]["role"] == "assistant"
    assert reasoning_rows[0]["kind"] == "assistant_process"
    assert reasoning_rows[0]["correlation"]["process_type"] == "reasoning"
    assert reasoning_rows[0]["correlation"]["message_id"] == "m-12"
    assert tool_rows[0]["kind"] == "assistant_process"
    assert tool_rows[0]["correlation"]["process_type"] == "tool_call"
    assert tool_rows[0]["text"] == "search(q=contract)"
    assert command_rows[0]["kind"] == "assistant_process"
    assert command_rows[0]["correlation"]["process_type"] == "command_execution"
    assert command_rows[0]["text"] == "python -m pytest -q tests/unit/test_chat_replay_derivation.py"


def test_assistant_intermediate_derivation_maps_to_assistant_message() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 14,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:05:00Z",
            "type": "assistant.message.intermediate",
            "data": {
                "message_id": "m-14",
                "summary": "Draft answer",
                "classification": "intermediate",
                "details": {"source": "live_semantic"},
                "text": "Draft answer body",
            },
            "meta": {"attempt": 2},
        }
    )

    assert rows[0]["role"] == "assistant"
    assert rows[0]["kind"] == "assistant_message"
    assert rows[0]["text"] == "Draft answer body"
    assert rows[0]["correlation"]["message_id"] == "m-14"


def test_assistant_message_promoted_derivation_emits_no_chat_row() -> None:
    rows = derive_chat_replay_rows_from_fcmp(
        {
            "seq": 15,
            "run_id": "run-chat-derive",
            "ts": "2026-03-04T10:05:30Z",
            "type": "assistant.message.promoted",
            "data": {
                "message_id": "m-15",
                "summary": "Promoted to final",
            },
            "meta": {"attempt": 2},
        }
    )
    assert rows == []
