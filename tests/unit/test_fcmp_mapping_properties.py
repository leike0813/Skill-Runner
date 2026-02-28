from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from server.models import RuntimeEventCategory, RuntimeEventSource
from server.runtime.protocol.factories import make_rasp_event
from server.runtime.protocol.event_protocol import build_fcmp_events, build_rasp_events
from tests.common.session_invariant_contract import (
    fcmp_state_changed_tuples,
    ordering_rules,
    paired_event_rules,
)


def _write_logs(logs_dir: Path, *, stdout: str = "", stderr: str = "") -> tuple[Path, Path]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "stdout.txt"
    stderr_path = logs_dir / "stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return stdout_path, stderr_path


def _build_fcmp(
    *,
    tmp_path: Path,
    run_id: str,
    status: str,
    attempt_number: int = 1,
    pending_interaction: Dict[str, Any] | None = None,
    interaction_history: List[Dict[str, Any]] | None = None,
    orchestrator_events: List[Dict[str, Any]] | None = None,
    effective_session_timeout_sec: int | None = None,
) -> List[Dict[str, Any]]:
    stdout_path, stderr_path = _write_logs(tmp_path / run_id / "logs")
    rasp_events = build_rasp_events(
        run_id=run_id,
        engine="codex",
        attempt_number=attempt_number,
        status=status,
        pending_interaction=pending_interaction,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status=status,
        status_updated_at="2026-02-24T00:00:00",
        pending_interaction=pending_interaction,
        interaction_history=interaction_history,
        orchestrator_events=orchestrator_events,
        effective_session_timeout_sec=effective_session_timeout_sec,
    )
    return [event.model_dump(mode="json") for event in fcmp_events]


def test_conversation_state_changed_events_follow_declared_mapping(tmp_path: Path) -> None:
    mapped = fcmp_state_changed_tuples()
    scenarios = [
        _build_fcmp(
            tmp_path=tmp_path,
            run_id="run-running",
            status="running",
            orchestrator_events=[
                {
                    "ts": "2026-02-24T00:00:00",
                    "attempt_number": 1,
                    "category": "lifecycle",
                    "type": "lifecycle.run.started",
                    "data": {"status": "running"},
                }
            ],
        ),
        _build_fcmp(
            tmp_path=tmp_path,
            run_id="run-waiting",
            status="waiting_user",
            pending_interaction={"interaction_id": 11, "kind": "open_text", "prompt": "continue?"},
            orchestrator_events=[
                {
                    "ts": "2026-02-24T00:00:01",
                    "attempt_number": 1,
                    "category": "interaction",
                    "type": "interaction.user_input.required",
                    "data": {"interaction_id": 11, "kind": "open_text"},
                }
            ],
        ),
        _build_fcmp(tmp_path=tmp_path, run_id="run-success", status="succeeded"),
        _build_fcmp(tmp_path=tmp_path, run_id="run-failed", status="failed"),
        _build_fcmp(tmp_path=tmp_path, run_id="run-canceled", status="canceled"),
    ]

    for events in scenarios:
        for event in events:
            if event["type"] != "conversation.state.changed":
                continue
            triple = (event["data"]["from"], event["data"]["to"], event["data"]["trigger"])
            assert triple in mapped


def test_paired_reply_and_auto_decide_events_require_state_change_pair(tmp_path: Path) -> None:
    rules = paired_event_rules()
    interaction_history = [
        {
            "interaction_id": 3,
            "event_type": "reply",
            "payload": {
                "response": {"answer": "ok"},
                "resolution_mode": "user_reply",
                "resolved_at": "2026-02-24T00:00:02",
            },
            "created_at": "2026-02-24T00:00:02",
        },
        {
            "interaction_id": 4,
            "event_type": "reply",
            "payload": {
                "response": {"answer": "auto"},
                "resolution_mode": "auto_decide_timeout",
                "resolved_at": "2026-02-24T00:00:03",
                "auto_decide_policy": "engine_judgement",
            },
            "created_at": "2026-02-24T00:00:03",
        },
    ]
    user_reply_events = _build_fcmp(
        tmp_path=tmp_path,
        run_id="run-reply-history-user",
        status="running",
        attempt_number=4,
        interaction_history=interaction_history,
        effective_session_timeout_sec=1200,
    )
    auto_decide_events = _build_fcmp(
        tmp_path=tmp_path,
        run_id="run-reply-history-auto",
        status="running",
        attempt_number=5,
        interaction_history=interaction_history,
        effective_session_timeout_sec=1200,
    )

    scenarios = {
        "interaction.reply.accepted": user_reply_events,
        "interaction.auto_decide.timeout": auto_decide_events,
    }
    for event_type, events in scenarios.items():
        required = rules[event_type]
        emitted = [idx for idx, evt in enumerate(events) if evt["type"] == event_type]
        assert emitted, f"missing paired event: {event_type}"
        for idx in emitted:
            assert any(
                later_idx > idx
                and events[later_idx]["type"] == "conversation.state.changed"
                and (
                    events[later_idx]["data"].get("from"),
                    events[later_idx]["data"].get("to"),
                    events[later_idx]["data"].get("trigger"),
                )
                == required
                for later_idx in range(idx + 1, len(events))
            )


def test_terminal_state_change_has_consistent_terminal_event(tmp_path: Path) -> None:
    scenarios = {
        "succeeded": "conversation.completed",
        "failed": "conversation.failed",
        "canceled": "conversation.failed",
    }
    for status, terminal_event_type in scenarios.items():
        events = _build_fcmp(tmp_path=tmp_path, run_id=f"run-terminal-{status}", status=status)
        for idx, event in enumerate(events):
            if event["type"] != "conversation.state.changed":
                continue
            if event["data"].get("to") != status:
                continue
            assert any(
                candidate["type"] == terminal_event_type
                for candidate in events[idx + 1 :]
            )
            break
        else:
            raise AssertionError(f"missing terminal state change for status={status}")


def test_waiting_user_state_requires_user_input_required_event(tmp_path: Path) -> None:
    assert "waiting_user_requires_input_event" in ordering_rules()
    events = _build_fcmp(
        tmp_path=tmp_path,
        run_id="run-waiting-pair",
        status="waiting_user",
        pending_interaction={"interaction_id": 7, "kind": "open_text", "prompt": "next"},
    )
    assert any(
        event["type"] == "conversation.state.changed"
        and event["data"].get("to") == "waiting_user"
        for event in events
    )
    assert any(event["type"] == "user.input.required" for event in events)


def test_fcmp_seq_is_monotonic_and_contiguous(tmp_path: Path) -> None:
    assert "seq_monotonic_contiguous" in ordering_rules()
    scenarios = [
        _build_fcmp(tmp_path=tmp_path, run_id="run-seq-running", status="running"),
        _build_fcmp(tmp_path=tmp_path, run_id="run-seq-waiting", status="waiting_user"),
        _build_fcmp(tmp_path=tmp_path, run_id="run-seq-succeeded", status="succeeded"),
    ]
    for events in scenarios:
        seqs = [int(event["seq"]) for event in events]
        assert seqs == list(range(1, len(events) + 1))


def test_reply_accepted_precedes_resumed_assistant_message() -> None:
    assert "reply_accepted_precedes_resumed_assistant" in ordering_rules()
    source = RuntimeEventSource(engine="codex", parser="test", confidence=0.95)
    rasp_events = [
        make_rasp_event(
            run_id="run-reply-order",
            seq=1,
            source=source,
            category=RuntimeEventCategory.LIFECYCLE,
            type_name="lifecycle.run.status",
            data={"status": "running"},
            attempt_number=2,
        ),
        make_rasp_event(
            run_id="run-reply-order",
            seq=2,
            source=source,
            category=RuntimeEventCategory.AGENT,
            type_name="agent.message.final",
            data={"message_id": "m_2_1", "text": "继续处理"},
            attempt_number=2,
        ),
    ]
    interaction_history = [
        {
            "interaction_id": 1,
            "event_type": "reply",
            "payload": {
                "response": {"text": "用户已回复"},
                "resolution_mode": "user_reply",
                "resolved_at": "2026-02-24T00:00:02",
            },
            "created_at": "2026-02-24T00:00:02",
        }
    ]
    events = [
        event.model_dump(mode="json")
        for event in build_fcmp_events(
            rasp_events,
            status="running",
            interaction_history=interaction_history,
        )
    ]
    idx_reply = next(i for i, evt in enumerate(events) if evt["type"] == "interaction.reply.accepted")
    idx_assistant = next(i for i, evt in enumerate(events) if evt["type"] == "assistant.message.final")
    assert idx_reply < idx_assistant
