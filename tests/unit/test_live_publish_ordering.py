from datetime import datetime
from pathlib import Path

import pytest

from server.runtime.observability.run_observability import RunObservabilityService
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.protocol.live_publish import FcmpEventPublisher, fcmp_event_publisher
from server.services.orchestration.job_orchestrator import JobOrchestrator


class _NoopMirrorWriter:
    def enqueue(self, *, run_dir: Path, attempt_number: int, row: dict) -> None:
        _ = run_dir
        _ = attempt_number
        _ = row


def _fcmp_row(*, run_id: str, type_name: str, data: dict, correlation: dict | None = None) -> dict:
    return {
        "protocol_version": "fcmp/1.0",
        "run_id": run_id,
        "seq": 0,
        "ts": datetime.utcnow().isoformat(),
        "engine": "codex",
        "type": type_name,
        "data": data,
        "meta": {"attempt": 1},
        "correlation": correlation or {},
        "raw_ref": None,
    }


def test_fcmp_publisher_buffers_challenge_until_method_selection_is_published(tmp_path: Path) -> None:
    run_id = "run-auth-order"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear(run_id)
    publisher = FcmpEventPublisher(mirror_writer=_NoopMirrorWriter())

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="auth.challenge.updated",
            data={
                "auth_session_id": "auth-1",
                "engine": "codex",
                "provider_id": "google",
                "challenge_kind": "callback_url",
                "phase": "challenge_active",
                "prompt": "Paste callback URL.",
                "instructions": "Paste callback URL to continue.",
                "accepts_chat_input": True,
                "input_kind": "callback_url",
                "last_error": None,
                "source_attempt": 1,
            },
            correlation={"auth_route": "multi_method"},
            ),
        )
    empty_replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert empty_replay["events"] == []

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="auth.required",
            data={
                "engine": "codex",
                "provider_id": None,
                "phase": "method_selection",
                "available_methods": ["callback", "device_auth"],
                "prompt": "Choose auth method.",
                "instructions": "Select an auth method to continue.",
                "last_error": None,
                "source_attempt": 1,
            },
        ),
    )
    replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in replay["events"]] == ["auth.required", "auth.challenge.updated"]
    assert [row["seq"] for row in replay["events"]] == [1, 2]


def test_fcmp_publisher_allows_single_method_challenge_without_selection(tmp_path: Path) -> None:
    run_id = "run-auth-single-method"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear(run_id)
    publisher = FcmpEventPublisher(mirror_writer=_NoopMirrorWriter())

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="auth.challenge.updated",
            data={
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "challenge_kind": "callback_url",
                "phase": "challenge_active",
                "prompt": "Paste callback URL.",
                "instructions": "Paste callback URL to continue.",
                "accepts_chat_input": True,
                "input_kind": "callback_url",
                "auth_method": "callback",
                "source_attempt": 1,
            },
        ),
    )
    replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in replay["events"]] == ["auth.challenge.updated"]


def test_fcmp_publisher_buffers_success_terminal_until_assistant_message_is_published(tmp_path: Path) -> None:
    run_id = "run-terminal-order"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear(run_id)
    publisher = FcmpEventPublisher(mirror_writer=_NoopMirrorWriter())

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="conversation.state.changed",
            data={
                "from": "running",
                "to": "succeeded",
                "trigger": "turn.succeeded",
                "updated_at": "2026-03-04T00:00:00Z",
                "pending_interaction_id": None,
                "terminal": {"status": "succeeded", "reason_code": "OUTPUT_VALIDATED", "diagnostics": []},
            },
        ),
    )
    empty_replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert empty_replay["events"] == []

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="assistant.message.final",
            data={"message_id": "m-1", "text": "done"},
        ),
    )
    replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in replay["events"]] == [
        "assistant.message.final",
        "conversation.state.changed",
    ]
    assert replay["events"][1]["data"]["terminal"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_orchestrator_waiting_user_event_keeps_prompt_before_state_in_live_and_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-waiting-order"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / ".state").mkdir(parents=True, exist_ok=True)
    (run_dir / ".state" / "state.json").write_text(
        '{"status":"waiting_user","current_attempt":1}',
        encoding="utf-8",
    )
    fcmp_live_journal.clear(run_id)
    monkeypatch.setattr(fcmp_event_publisher, "_mirror_writer", _NoopMirrorWriter())

    orchestrator = JobOrchestrator()
    orchestrator._append_orchestrator_event(
        run_dir=run_dir,
        attempt_number=1,
        category="interaction",
        type_name="interaction.user_input.required",
        data={
            "interaction_id": 7,
            "kind": "open_text",
        },
        engine_name="codex",
    )

    live_replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in live_replay["events"]] == [
        "user.input.required",
        "conversation.state.changed",
    ]
    assert live_replay["events"][1]["data"]["to"] == "waiting_user"

    history_payload = await RunObservabilityService().get_event_history_payload(
        run_dir=run_dir,
        request_id=None,
        from_seq=1,
        to_seq=None,
        from_ts=None,
        to_ts=None,
    )
    assert [row["type"] for row in history_payload["events"]] == [
        "user.input.required",
        "conversation.state.changed",
    ]


def test_orchestrator_auth_selection_is_published_before_challenge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-auth-orchestrator-order"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear(run_id)
    monkeypatch.setattr(fcmp_event_publisher, "_mirror_writer", _NoopMirrorWriter())
    orchestrator = JobOrchestrator()

    orchestrator._append_orchestrator_event(
        run_dir=run_dir,
        attempt_number=1,
        category="interaction",
        type_name="auth.method.selection.required",
        data={
            "engine": "codex",
            "provider_id": "google",
            "phase": "method_selection",
            "available_methods": ["callback", "device_auth"],
            "prompt": "Choose auth method.",
            "instructions": "Select an auth method to continue.",
            "source_attempt": 1,
        },
        engine_name="codex",
    )

    orchestrator._append_orchestrator_event(
        run_dir=run_dir,
        attempt_number=1,
        category="interaction",
        type_name="auth.challenge.updated",
        data={
            "auth_session_id": "auth-1",
            "engine": "codex",
            "provider_id": "google",
            "challenge_kind": "callback_url",
            "phase": "challenge_active",
            "prompt": "Paste callback URL.",
            "instructions": "Paste callback URL to continue.",
            "accepts_chat_input": True,
            "input_kind": "callback_url",
            "source_attempt": 1,
        },
        engine_name="codex",
    )

    replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in replay["events"]] == [
        "auth.required",
        "conversation.state.changed",
        "auth.challenge.updated",
    ]


def test_orchestrator_auth_busy_maps_to_diagnostic_instead_of_challenge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-auth-busy-diagnostic"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear(run_id)
    monkeypatch.setattr(fcmp_event_publisher, "_mirror_writer", _NoopMirrorWriter())
    orchestrator = JobOrchestrator()

    orchestrator._append_orchestrator_event(
        run_dir=run_dir,
        attempt_number=1,
        category="interaction",
        type_name="auth.session.busy",
        data={
            "engine": "opencode",
            "provider_id": "google",
            "phase": "method_selection",
            "available_methods": ["callback"],
            "prompt": "Authentication is required for provider 'google'. Choose how to continue.",
            "instructions": "Select an authentication method to continue. Previous error: Auth session already active: auth-1",
            "last_error": "Auth session already active: auth-1",
            "source_attempt": 1,
            "ui_hints": {"widget": "choice"},
        },
        engine_name="opencode",
    )

    replay = fcmp_live_journal.replay(run_id=run_id, after_seq=0)
    assert [row["type"] for row in replay["events"]] == ["diagnostic.warning"]
    assert replay["events"][0]["data"]["code"] == "AUTH_SESSION_BUSY"
