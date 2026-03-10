import json
from datetime import datetime
from pathlib import Path

import pytest

from server.runtime.observability.run_observability import RunObservabilityService
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.protocol.live_publish import FcmpEventPublisher, RaspAuditMirrorWriter, fcmp_event_publisher
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
async def test_fcmp_publisher_drain_mirror_flushes_audit_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run-drain-mirror"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    drain_calls: list[str | None] = []

    class _DrainAwareMirrorWriter:
        def enqueue(self, *, run_dir: Path, attempt_number: int, row: dict) -> None:
            path = run_dir / ".audit" / f"fcmp_events.{attempt_number}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(row, ensure_ascii=False))
                fp.write("\n")

        async def drain(self, *, run_id: str | None = None) -> None:
            drain_calls.append(run_id)

    monkeypatch.setattr(
        "server.runtime.protocol.live_publish.chat_replay_publisher.publish_from_fcmp",
        lambda **_kwargs: None,
    )
    publisher = FcmpEventPublisher(mirror_writer=_DrainAwareMirrorWriter())

    publisher.publish(
        run_dir=run_dir,
        event=_fcmp_row(
            run_id=run_id,
            type_name="assistant.message.final",
            data={"message_id": "m-1", "text": "done"},
        ),
    )
    await publisher.drain_mirror(run_id=run_id)

    audit_path = run_dir / ".audit" / "fcmp_events.1.jsonl"
    assert audit_path.exists()
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["type"] == "assistant.message.final"
    assert drain_calls == [run_id]


@pytest.mark.asyncio
async def test_rasp_audit_mirror_writer_persists_jsonl_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-rasp-writer"
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = RaspAuditMirrorWriter()
    attempt_number = 1
    rows = [
        {
            "protocol_version": "rasp/1.0",
            "run_id": run_dir.name,
            "seq": index + 1,
            "ts": datetime.utcnow().isoformat(),
            "source": {"engine": "gemini", "parser": "live_raw", "confidence": 1.0},
            "event": {"category": "raw", "type": "raw.stderr"},
            "data": {"line": f"line-{index}"},
            "correlation": {},
            "attempt_number": attempt_number,
            "raw_ref": {
                "attempt_number": attempt_number,
                "stream": "stderr",
                "byte_from": index * 10,
                "byte_to": index * 10 + 6,
                "encoding": "utf-8",
            },
        }
        for index in range(8)
    ]

    for row in rows:
        await writer.append_row(run_dir=run_dir, attempt_number=attempt_number, row=row)

    path = run_dir / ".audit" / "events.1.jsonl"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == len(rows)
    decoded = [json.loads(line) for line in lines]
    assert {item["seq"] for item in decoded} == set(range(1, 9))


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
