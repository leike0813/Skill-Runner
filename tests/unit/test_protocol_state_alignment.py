import json
from pathlib import Path

from server.runtime.protocol.event_protocol import build_fcmp_events, build_rasp_events
from server.runtime.session.statechart import SessionEvent, build_transition_index
from tests.common.session_invariant_contract import fcmp_state_changed_tuples


def _write_logs(logs_dir: Path) -> tuple[Path, Path]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "stdout.txt"
    stderr_path = logs_dir / "stderr.txt"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    return stdout_path, stderr_path


def test_waiting_user_protocol_events_align_with_state_transition(tmp_path: Path) -> None:
    mapped_state_changed = fcmp_state_changed_tuples()
    transitions = build_transition_index()
    assert ("running", SessionEvent.TURN_NEEDS_INPUT) in transitions
    assert transitions[("running", SessionEvent.TURN_NEEDS_INPUT)].target == "waiting_user"

    stdout_path, stderr_path = _write_logs(tmp_path / "run-waiting" / "logs")
    pending = {"interaction_id": 1, "kind": "open_text", "prompt": "continue?"}
    rasp_events = build_rasp_events(
        run_id="run-waiting",
        engine="codex",
        attempt_number=1,
        status="waiting_user",
        pending_interaction=pending,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_user",
        status_updated_at="2026-02-24T00:00:00",
        pending_interaction=pending,
    )

    assert any(
        event.event.type == "lifecycle.run.status" and event.data.get("status") == "waiting_user"
        for event in rasp_events
    )
    assert any(event.event.type == "interaction.user_input.required" for event in rasp_events)
    assert any(event.type == "user.input.required" for event in fcmp_events)
    waiting_state_changes = [
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "waiting_user"
    ]
    assert waiting_state_changes
    for event in waiting_state_changes:
        triple = (event.data.get("from"), event.data.get("to"), event.data.get("trigger"))
        assert triple in mapped_state_changed


def test_terminal_protocol_events_align_with_state_transitions(tmp_path: Path) -> None:
    mapped_state_changed = fcmp_state_changed_tuples()
    transitions = build_transition_index()
    assert ("running", SessionEvent.TURN_SUCCEEDED) in transitions
    assert ("running", SessionEvent.TURN_FAILED) in transitions
    assert transitions[("running", SessionEvent.TURN_SUCCEEDED)].target == "succeeded"
    assert transitions[("running", SessionEvent.TURN_FAILED)].target == "failed"

    succeeded_stdout, succeeded_stderr = _write_logs(tmp_path / "run-succeeded" / "logs")
    succeeded_rasp = build_rasp_events(
        run_id="run-succeeded",
        engine="codex",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=succeeded_stdout,
        stderr_path=succeeded_stderr,
    )
    succeeded_fcmp = build_fcmp_events(
        succeeded_rasp,
        status="succeeded",
        status_updated_at="2026-02-24T00:00:00",
    )
    assert any(event.type == "conversation.completed" for event in succeeded_fcmp)
    succeeded_state_changes = [
        event
        for event in succeeded_fcmp
        if event.type == "conversation.state.changed" and event.data.get("to") == "succeeded"
    ]
    assert succeeded_state_changes
    for event in succeeded_state_changes:
        triple = (event.data.get("from"), event.data.get("to"), event.data.get("trigger"))
        assert triple in mapped_state_changed

    failed_stdout, failed_stderr = _write_logs(tmp_path / "run-failed" / "logs")
    failed_stderr.write_text(json.dumps({"error": "boom"}), encoding="utf-8")
    failed_rasp = build_rasp_events(
        run_id="run-failed",
        engine="codex",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=failed_stdout,
        stderr_path=failed_stderr,
    )
    failed_fcmp = build_fcmp_events(
        failed_rasp,
        status="failed",
        status_updated_at="2026-02-24T00:00:00",
    )
    assert any(event.type == "conversation.failed" for event in failed_fcmp)
    failed_state_changes = [
        event
        for event in failed_fcmp
        if event.type == "conversation.state.changed" and event.data.get("to") == "failed"
    ]
    assert failed_state_changes
    for event in failed_state_changes:
        triple = (event.data.get("from"), event.data.get("to"), event.data.get("trigger"))
        assert triple in mapped_state_changed
