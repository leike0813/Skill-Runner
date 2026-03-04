import json
from pathlib import Path

from server.runtime.chat_replay.live_journal import chat_replay_live_journal
from server.runtime.chat_replay.publisher import ChatReplayPublisher


class _NoopMirrorWriter:
    def enqueue(self, *, run_dir: Path, row: dict) -> None:
        _ = run_dir
        _ = row


def test_chat_replay_publisher_bootstraps_seq_from_audit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-chat-publisher"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "chat_replay.jsonl").write_text(
        json.dumps(
            {
                "seq": 4,
                "run_id": "run-chat-publisher",
                "attempt": 1,
                "role": "user",
                "kind": "interaction_reply",
                "text": "old",
                "created_at": "2026-03-04T10:00:00Z",
                "correlation": {},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    chat_replay_live_journal.clear("run-chat-publisher")
    publisher = ChatReplayPublisher(mirror_writer=_NoopMirrorWriter())

    published = publisher.publish(
        run_dir=run_dir,
        event={
            "protocol_version": "chat-replay/1.0",
            "seq": 0,
            "run_id": "run-chat-publisher",
            "attempt": 2,
            "role": "assistant",
            "kind": "assistant_final",
            "text": "new",
            "created_at": "2026-03-04T10:05:00Z",
            "correlation": {"fcmp_seq": 10},
        },
    )

    assert published["seq"] == 5
    payload = chat_replay_live_journal.replay(run_id="run-chat-publisher", after_seq=0)
    assert payload["events"][-1]["text"] == "new"
