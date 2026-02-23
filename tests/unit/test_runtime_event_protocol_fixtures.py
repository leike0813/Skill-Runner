import json
from pathlib import Path

import pytest

from server.services.runtime_event_protocol import build_rasp_events


@pytest.mark.parametrize(
    "engine,status,stdout_text,stderr_text,expected_parser,expected_message,expected_session_id",
    [
        (
            "codex",
            "succeeded",
            '{"type":"thread.started","thread_id":"t-codex"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"codex message"}}\n'
            '{"type":"turn.completed"}\n',
            "",
            "codex_ndjson",
            "codex message",
            "t-codex",
        ),
        (
            "gemini",
            "succeeded",
            "YOLO mode enabled\n",
            json.dumps({"session_id": "t-gemini", "response": "gemini message"}, ensure_ascii=False),
            "gemini_json",
            "gemini message",
            "t-gemini",
        ),
        (
            "iflow",
            "waiting_user",
            '<Execution Info>{"session-id":"t-iflow"}</Execution Info>\niflow message\n',
            "",
            "iflow_text",
            "iflow message",
            "t-iflow",
        ),
        (
            "opencode",
            "succeeded",
            '{"type":"text","part":{"text":"opencode message"}}\n',
            "",
            "opencode_ndjson",
            "opencode message",
            None,
        ),
    ],
)
def test_runtime_protocol_parsers_and_completion_state(
    tmp_path: Path,
    engine: str,
    status: str,
    stdout_text: str,
    stderr_text: str,
    expected_parser: str,
    expected_message: str,
    expected_session_id: str | None,
):
    run_dir = tmp_path / f"run-{engine}"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "stdout.txt"
    stderr_path = logs_dir / "stderr.txt"
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    completion_state = (
        "awaiting_user_input" if status == "waiting_user" else "completed"
    )
    rasp_events = build_rasp_events(
        run_id=f"run-{engine}",
        engine=engine,
        attempt_number=1,
        status=status,
        pending_interaction={"interaction_id": 7, "prompt": "continue?"}
        if status == "waiting_user"
        else None,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        completion={"state": completion_state, "reason_code": "TEST_FIXTURE"},
    )

    assert rasp_events
    assert all(event.source.parser == expected_parser for event in rasp_events)
    assert any(event.event.type == "agent.message.final" for event in rasp_events)
    assert any(
        event.event.type == "agent.message.final"
        and expected_message in str(event.data.get("text", ""))
        for event in rasp_events
    )
    assert any(
        event.event.type == "lifecycle.completion.state"
        and event.data.get("state") == completion_state
        for event in rasp_events
    )
    if expected_session_id is None:
        assert not any(event.correlation.get("session_id") for event in rasp_events)
    else:
        assert any(
            event.correlation.get("session_id") == expected_session_id
            for event in rasp_events
        )
