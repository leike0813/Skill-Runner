from server.runtime.observability.fcmp_live_journal import fcmp_live_journal


def test_fcmp_live_journal_publish_and_replay() -> None:
    run_id = "run-live-journal-basic"
    fcmp_live_journal.clear(run_id)
    fcmp_live_journal.publish(
        run_id=run_id,
        row={"seq": 1, "type": "assistant.message.final", "data": {"text": "hello"}},
    )
    fcmp_live_journal.publish(
        run_id=run_id,
        row={
            "seq": 2,
            "type": "conversation.state.changed",
            "data": {"from": "running", "to": "succeeded", "trigger": "turn.succeeded"},
        },
        terminal=True,
    )

    payload = fcmp_live_journal.replay(run_id=run_id, after_seq=0)

    assert payload["cursor_floor"] == 1
    assert payload["cursor_ceiling"] == 2
    assert [row["seq"] for row in payload["events"]] == [1, 2]


def test_fcmp_live_journal_replay_after_cursor() -> None:
    run_id = "run-live-journal-after-cursor"
    fcmp_live_journal.clear(run_id)
    for seq in range(1, 4):
        fcmp_live_journal.publish(
            run_id=run_id,
            row={"seq": seq, "type": "diagnostic.warning", "data": {"code": f"C{seq}"}},
        )

    payload = fcmp_live_journal.replay(run_id=run_id, after_seq=2)

    assert [row["seq"] for row in payload["events"]] == [3]
