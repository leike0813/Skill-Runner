from server.runtime.chat_replay.live_journal import chat_replay_live_journal


def test_chat_replay_live_journal_publish_and_replay() -> None:
    run_id = "run-chat-journal-basic"
    chat_replay_live_journal.clear(run_id)
    chat_replay_live_journal.publish(
        run_id=run_id,
        row={"seq": 1, "role": "user", "kind": "interaction_reply", "text": "hello"},
    )
    chat_replay_live_journal.publish(
        run_id=run_id,
        row={"seq": 2, "role": "assistant", "kind": "assistant_final", "text": "world"},
    )

    payload = chat_replay_live_journal.replay(run_id=run_id, after_seq=0)

    assert payload["cursor_floor"] == 1
    assert payload["cursor_ceiling"] == 2
    assert [row["seq"] for row in payload["events"]] == [1, 2]


def test_chat_replay_live_journal_replay_after_cursor() -> None:
    run_id = "run-chat-journal-after"
    chat_replay_live_journal.clear(run_id)
    for seq in range(1, 4):
        chat_replay_live_journal.publish(
            run_id=run_id,
            row={"seq": seq, "role": "system", "kind": "orchestration_notice", "text": f"n-{seq}"},
        )

    payload = chat_replay_live_journal.replay(run_id=run_id, after_seq=2)

    assert [row["seq"] for row in payload["events"]] == [3]
