import json
import base64
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from server.runtime.protocol.event_protocol import write_jsonl
from server.runtime.protocol.factories import make_fcmp_event, make_fcmp_state_changed
from server.runtime.protocol.factories import make_rasp_event
from server.models import RuntimeEventCategory, RuntimeEventRef, RuntimeEventSource
from server.services.orchestration.run_recovery_service import run_recovery_service
from server.services.orchestration.run_store import RunStore
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.observability.rasp_live_journal import rasp_live_journal
from server.runtime.observability.run_observability import RunObservabilityService


def _write_state_file(run_dir: Path, status: str) -> None:
    state_path = run_dir / ".state" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "request_id": run_dir.name,
                "run_id": run_dir.name,
                "status": status,
                "updated_at": "2026-01-01T00:00:00",
                "current_attempt": 1,
                "state_phase": {"waiting_auth_phase": None, "dispatch_phase": None},
                "pending": {"owner": None, "interaction_id": None, "auth_session_id": None, "payload": None},
                "resume": {
                    "resume_ticket_id": None,
                    "resume_cause": None,
                    "source_attempt": None,
                    "target_attempt": None,
                },
                "runtime": {},
                "error": None,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_list_runs_and_get_logs_tail(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    (run_dir / ".audit").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / ".audit" / "meta.1.json").write_text("{}", encoding="utf-8")
    (run_dir / ".audit" / "stdout.1.log").write_text("line1\nline2\n", encoding="utf-8")
    (run_dir / ".audit" / "stderr.1.log").write_text("err1\n", encoding="utf-8")
    _write_state_file(run_dir, "running")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_requests_with_runs",
        AsyncMock(return_value=[
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo",
                "engine": "gemini",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request_with_run",
        AsyncMock(side_effect=lambda request_id: {
            "request_id": request_id,
            "run_id": "run-1",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "running",
        }),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    service = RunObservabilityService()
    rows = await service.list_runs()
    assert len(rows) == 1
    assert rows[0]["request_id"] == "req-1"
    assert rows[0]["status"] == "running"

    tail = await service.get_logs_tail("req-1", max_bytes=5)
    assert tail["poll"] is True
    assert tail["stdout"].endswith("ne2\n")
    assert "err1" in tail["stderr"]


@pytest.mark.asyncio
async def test_list_runs_reconciles_waiting_auth_before_render(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_auth")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_requests_with_runs",
        AsyncMock(
            return_value=[
                {
                    "request_id": "req-auth",
                    "run_id": "run-auth",
                    "skill_id": "demo",
                    "engine": "codex",
                    "request_created_at": "2026-01-01T00:00:00",
                    "run_status": "waiting_auth",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    async def _reconcile(request_id: str) -> bool:
        assert request_id == "req-auth"
        _write_state_file(run_dir, "failed")
        return True

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.waiting_auth_reconciler",
        _reconcile,
    )

    service = RunObservabilityService()
    rows = await service.list_runs()

    assert rows[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_get_run_detail_redrives_queued_resume_ticket(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-queued"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "queued")
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request_with_run",
        AsyncMock(
            return_value={
                "request_id": "req-queued",
                "run_id": "run-queued",
                "skill_id": "demo",
                "engine": "codex",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "queued",
                "runtime_options": {"execution_mode": "interactive"},
                "effective_runtime_options": {"execution_mode": "interactive"},
                "client_metadata": {"conversation_mode": "session"},
            }
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(
            return_value={
                "request_id": "req-queued",
                "run_id": "run-queued",
                "skill_id": "demo",
                "engine": "codex",
            }
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=None),
    )
    redrive = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_recovery_service.run_recovery_service.redrive_resume_ticket_if_needed",
        redrive,
    )

    service = RunObservabilityService()
    detail = await service.get_run_detail("req-queued")

    assert detail["status"] == "queued"
    redrive.assert_awaited_once()
    await_args = redrive.await_args
    assert await_args is not None
    assert await_args.kwargs["request_id"] == "req-queued"
    assert await_args.kwargs["run_id"] == "run-queued"
    assert await_args.kwargs["recovery_reason"] == "resume_ticket_redriven_online"


@pytest.mark.asyncio
async def test_missing_run_dir_queued_resume_reconciles_failed_in_list_and_detail(monkeypatch, tmp_path: Path):
    local_store = RunStore(db_path=tmp_path / "runs.db")
    await local_store.create_request(
        request_id="req-orphan",
        skill_id="demo",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        effective_runtime_options={"execution_mode": "interactive"},
        client_metadata={"conversation_mode": "session"},
        input_data={},
    )
    await local_store.update_request_run_id("req-orphan", "run-orphan")
    await local_store.create_run("run-orphan", None, "queued")
    await local_store.issue_resume_ticket(
        "req-orphan",
        cause="interaction_reply",
        source_attempt=1,
        target_attempt=2,
        payload={"interaction_id": 1, "response": {"text": "hello"}, "resolution_mode": "user_reply"},
    )

    async def _redrive(**kwargs):
        return await run_recovery_service.redrive_resume_ticket_if_needed(
            **kwargs,
            workspace_backend=type("Workspace", (), {"get_run_dir": lambda self, _run_id: None})(),
            resume_run_job=lambda **_payload: None,
            recovery_reason="resume_ticket_redriven_online",
        )

    monkeypatch.setattr("server.runtime.observability.run_observability.run_store", local_store)
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: None,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.queued_resume_redriver",
        _redrive,
    )

    service = RunObservabilityService()
    rows = await service.list_runs()
    detail = await service.get_run_detail("req-orphan")

    assert rows[0]["status"] == "failed"
    assert rows[0]["recovery_state"] == "failed_reconciled"
    assert rows[0]["recovery_reason"] == "missing_run_dir_before_resume_redrive"
    assert detail["status"] == "failed"
    assert detail["recovery_state"] == "failed_reconciled"
    assert detail["recovery_reason"] == "missing_run_dir_before_resume_redrive"
    assert detail["entries"] == []


@pytest.mark.asyncio
async def test_get_run_detail_hides_denylisted_node_modules(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-tree"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    (run_dir / "app").mkdir(parents=True, exist_ok=True)
    (run_dir / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (run_dir / "workspace" / "node_modules" / "pkg").mkdir(parents=True, exist_ok=True)
    (run_dir / "workspace" / "node_modules" / "pkg" / "index.js").write_text("module.exports={};", encoding="utf-8")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request_with_run",
        AsyncMock(
            return_value={
                "request_id": "req-tree",
                "run_id": "run-tree",
                "skill_id": "demo",
                "engine": "opencode",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=None),
    )

    service = RunObservabilityService()
    detail = await service.get_run_detail("req-tree")
    rel_paths = [entry["rel_path"] for entry in detail["entries"]]

    assert "app/main.py" in rel_paths
    assert all("node_modules" not in path for path in rel_paths)


@pytest.mark.asyncio
async def test_run_file_preview_rejects_filtered_node_modules_path(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-preview"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    (run_dir / "workspace" / "node_modules" / "pkg").mkdir(parents=True, exist_ok=True)
    (run_dir / "workspace" / "node_modules" / "pkg" / "index.js").write_text("secret", encoding="utf-8")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request_with_run",
        AsyncMock(
            return_value={
                "request_id": "req-preview",
                "run_id": "run-preview",
                "skill_id": "demo",
                "engine": "opencode",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=None),
    )

    service = RunObservabilityService()
    with pytest.raises(ValueError, match="path is filtered"):
        await service.build_run_file_preview("req-preview", "workspace/node_modules/pkg/index.js")


def test_read_log_increment_supports_offsets_and_chunking(tmp_path: Path):
    log_path = tmp_path / "stdout.txt"
    log_path.write_text("abcdef", encoding="utf-8")
    service = RunObservabilityService()

    chunk1 = service.read_log_increment(log_path, from_offset=0, max_bytes=2)
    assert chunk1 == {"from": 0, "to": 2, "chunk": "ab"}

    chunk2 = service.read_log_increment(log_path, from_offset=2, max_bytes=3)
    assert chunk2 == {"from": 2, "to": 5, "chunk": "cde"}


@pytest.mark.asyncio
async def test_event_history_prefers_live_journal_when_audit_missing(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-history"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    fcmp_live_journal.clear(run_dir.name)
    fcmp_live_journal.publish(
        run_id=run_dir.name,
        row={
            "protocol_version": "fcmp/1.0",
            "run_id": run_dir.name,
            "seq": 1,
            "ts": "2026-03-04T00:00:00Z",
            "engine": "codex",
            "type": "assistant.message.final",
            "data": {"message_id": "m_1", "text": "hello"},
            "meta": {"attempt": 1, "local_seq": 1},
            "correlation": {"publish_id": "pub-1"},
            "raw_ref": None,
        },
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value=None),
    )

    service = RunObservabilityService()
    payload = await service.get_event_history_payload(
        run_dir=run_dir,
        request_id=None,
        from_seq=1,
        to_seq=None,
        from_ts=None,
        to_ts=None,
    )

    assert payload["source"] == "live"
    assert payload["events"][0]["data"]["text"] == "hello"


@pytest.mark.asyncio
async def test_iter_sse_events_replays_live_journal_without_materializing_audit(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-sse"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_user")
    fcmp_live_journal.clear(run_dir.name)
    fcmp_live_journal.publish(
        run_id=run_dir.name,
        row={
            "protocol_version": "fcmp/1.0",
            "run_id": run_dir.name,
            "seq": 1,
            "ts": "2026-03-04T00:00:00Z",
            "engine": "codex",
            "type": "assistant.message.final",
            "data": {"message_id": "m_1", "text": "live only"},
            "meta": {"attempt": 1, "local_seq": 1},
            "correlation": {"publish_id": "pub-live"},
            "raw_ref": None,
        },
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        RunObservabilityService,
        "_read_pending_interaction_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        RunObservabilityService,
        "_read_pending_auth_session_id",
        AsyncMock(return_value=None),
    )

    service = RunObservabilityService()
    iterator = service.iter_sse_events(run_dir=run_dir, request_id=None, cursor=0)
    events = []
    async for item in iterator:
        events.append(item)

    assert events[0]["event"] == "snapshot"
    assert events[1]["event"] == "chat_event"
    assert events[1]["data"]["data"]["text"] == "live only"


@pytest.mark.asyncio
async def test_list_event_history_filters_invalid_fcmp_rows(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    fcmp_path = audit_dir / "fcmp_events.1.jsonl"
    fcmp_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "protocol_version": "fcmp/1.0",
                        "run_id": "run-history",
                        "seq": 1,
                        "ts": "2026-02-24T00:00:00",
                        "engine": "codex",
                        "type": "conversation.state.changed",
                        "data": {
                            "from": "queued",
                            "to": "running",
                            "trigger": "turn.started",
                            "updated_at": "2026-02-24T00:00:00",
                            "pending_interaction_id": None,
                        },
                        "meta": {"attempt": 1},
                    }
                ),
                json.dumps(
                    {
                        "protocol_version": "fcmp/1.0",
                        "run_id": "run-history",
                        "seq": 2,
                        "ts": "2026-02-24T00:00:01",
                        "engine": "codex",
                        "type": "conversation.state.changed",
                        "data": {"to": "running"},
                        "meta": {"attempt": 1},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    async def _materialize(_self, **_kwargs):
        return {"rasp_events": [], "fcmp_events": []}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._materialize_protocol_stream",
        _materialize,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._read_status_payload",
        lambda self, _run_dir: {"status": "succeeded"},
    )
    service = RunObservabilityService()
    rows = await service.list_event_history(run_dir=run_dir, request_id="req-hist")
    assert len(rows) == 1
    assert rows[0]["seq"] == 1


@pytest.mark.asyncio
async def test_list_event_history_delegates_to_fcmp_protocol_history(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history-delegate"
    run_dir.mkdir(parents=True, exist_ok=True)
    service = RunObservabilityService()
    captured: dict[str, object] = {}

    async def _list_protocol_history(**kwargs):
        captured.update(kwargs)
        return {"events": [{"seq": 9}], "attempt": 1, "available_attempts": [1]}

    monkeypatch.setattr(service, "list_protocol_history", _list_protocol_history)
    rows = await service.list_event_history(run_dir=run_dir, request_id="req-1", from_seq=None, to_seq=None)
    assert rows == [{"seq": 1, "meta": {"local_seq": 9}}]
    assert captured["stream"] == "fcmp"
    assert captured["request_id"] == "req-1"
    assert captured["from_seq"] is None
    assert captured["to_seq"] is None


@pytest.mark.asyncio
async def test_list_protocol_history_rejects_unknown_stream(tmp_path: Path):
    run_dir = tmp_path / "run-history-invalid-stream"
    run_dir.mkdir(parents=True, exist_ok=True)
    service = RunObservabilityService()
    with pytest.raises(ValueError, match="stream must be one of"):
        await service.list_protocol_history(
            run_dir=run_dir,
            request_id="req-1",
            stream="unknown",
        )


@pytest.mark.asyncio
async def test_list_protocol_history_rasp_terminal_uses_audit_only(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-terminal-rasp"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "succeeded")
    write_jsonl(
        audit_dir / "events.1.jsonl",
        [
            make_rasp_event(
                run_id=run_dir.name,
                seq=1,
                source=RuntimeEventSource(engine="gemini", parser="gemini_json", confidence=0.8),
                category=RuntimeEventCategory.RAW,
                type_name="raw.stderr",
                data={"line": "audit-block"},
                attempt_number=1,
                raw_ref=RuntimeEventRef(
                    attempt_number=1,
                    stream="stderr",
                    byte_from=0,
                    byte_to=10,
                    encoding="utf-8",
                ),
            ).model_dump(mode="json")
        ],
    )
    write_jsonl(audit_dir / "fcmp_events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")

    rasp_live_journal.clear(run_dir.name)
    rasp_live_journal.publish(
        run_id=run_dir.name,
        row=make_rasp_event(
            run_id=run_dir.name,
            seq=1,
            source=RuntimeEventSource(engine="gemini", parser="live_raw", confidence=1.0),
            category=RuntimeEventCategory.RAW,
            type_name="raw.stderr",
            data={"line": "live-fragment"},
            attempt_number=1,
            raw_ref=RuntimeEventRef(
                attempt_number=1,
                stream="stderr",
                byte_from=0,
                byte_to=12,
                encoding="utf-8",
            ),
        ).model_dump(mode="json"),
    )

    service = RunObservabilityService()
    monkeypatch.setattr(
        service,
        "_resolve_attempt_number",
        AsyncMock(side_effect=[1, 1]),
    )
    flush_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.flush_live_audit_mirrors",
        flush_mock,
    )

    payload = await service.list_protocol_history(
        run_dir=run_dir,
        request_id="req-terminal",
        stream="rasp",
        from_seq=None,
        to_seq=None,
        from_ts=None,
        to_ts=None,
        attempt=None,
        limit=200,
    )

    assert payload["source"] == "audit"
    assert len(payload["events"]) == 1
    assert payload["events"][0]["data"]["line"] == "audit-block"
    flush_mock.assert_awaited_once_with(run_id=run_dir.name)


@pytest.mark.asyncio
async def test_list_protocol_history_fcmp_does_not_trigger_materialize(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-no-materialize"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="queued",
                    target_state="running",
                    trigger="turn.started",
                    updated_at="2026-03-10T00:00:00Z",
                    pending_interaction_id=None,
                ),
                attempt_number=1,
            ).model_dump(mode="json")
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    materialize_mock = AsyncMock(return_value={"rasp_events": [], "fcmp_events": []})

    service = RunObservabilityService()
    monkeypatch.setattr(
        service,
        "_resolve_attempt_number",
        AsyncMock(side_effect=[1, 1]),
    )
    monkeypatch.setattr(service, "_materialize_protocol_stream", materialize_mock)

    payload = await service.list_protocol_history(
        run_dir=run_dir,
        request_id=None,
        stream="fcmp",
        from_seq=None,
        to_seq=None,
        from_ts=None,
        to_ts=None,
        attempt=None,
        limit=200,
    )

    assert payload["events"]
    materialize_mock.assert_not_awaited()


def _patch_protocol_defaults(monkeypatch, *, status: str, execution_mode: str = "auto") -> None:
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_auth",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "codex", "runtime_options": {"execution_mode": execution_mode}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=1200),
    )
    _ = status


@pytest.mark.asyncio
async def test_iter_sse_events_chat_only_for_terminal_status(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-protocol"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="codex",
                type_name="assistant.message.final",
                data={"message_id": "m-1", "text": "hello from codex"},
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=2,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="running",
                    target_state="succeeded",
                    trigger="turn.succeeded",
                    updated_at="2026-03-10T00:00:01Z",
                    pending_interaction_id=None,
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "succeeded")
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-protocol",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    assert events
    assert events[0]["event"] == "snapshot"
    event_names = {item["event"] for item in events}
    assert "chat_event" in event_names
    assert event_names.isdisjoint({"run_event", "status", "stdout", "stderr", "end"})

    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "assistant.message.final" for evt in chat_events)
    assert any(
        evt["type"] == "conversation.state.changed" and evt["data"].get("to") == "succeeded"
        for evt in chat_events
    )


@pytest.mark.asyncio
async def test_iter_sse_events_waiting_user_chat_only(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-wait"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="codex",
                type_name="user.input.required",
                data={"interaction_id": 7, "kind": "open_text", "prompt": "请继续输入"},
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=2,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="running",
                    target_state="waiting_user",
                    trigger="interaction.user_input.required",
                    updated_at="2026-03-10T00:00:01Z",
                    pending_interaction_id=7,
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "waiting_user")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        AsyncMock(return_value={"interaction_id": 7, "kind": "open_text", "prompt": "请继续输入"}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "codex", "runtime_options": {"execution_mode": "interactive"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=1200),
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-wait",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    assert events[0]["event"] == "snapshot"
    assert events[0]["data"]["pending_interaction_id"] == 7
    assert all(evt["event"] != "end" for evt in events)
    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "user.input.required" for evt in chat_events)
    assert any(
        evt["type"] == "conversation.state.changed" and evt["data"].get("to") == "waiting_user"
        for evt in chat_events
    )


@pytest.mark.asyncio
async def test_iter_sse_events_drains_trailing_waiting_user_chat_events(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-wait-drain"
    (run_dir / ".audit").mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_user")

    async def _get_event_history_payload(self, **kwargs):
        _ = self
        from_seq = kwargs.get("from_seq")
        if from_seq == 1:
            if not hasattr(_get_event_history_payload, "called"):
                _get_event_history_payload.called = True
                return {"events": [], "source": "live", "cursor_floor": 0, "cursor_ceiling": 0}
            return {
                "events": [
                    {
                        "seq": 1,
                        "type": "assistant.message.final",
                        "data": {"message_id": "m_1", "text": "hello after drain"},
                        "meta": {"attempt": 1},
                    },
                    {
                        "seq": 2,
                        "type": "user.input.required",
                        "data": {"interaction_id": 7, "kind": "free_text", "prompt": "please continue"},
                        "meta": {"attempt": 1},
                    },
                ],
                "source": "live",
                "cursor_floor": 1,
                "cursor_ceiling": 2,
            }
        return {"events": [], "source": "live", "cursor_floor": 0, "cursor_ceiling": 0}

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService.get_event_history_payload",
        _get_event_history_payload,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._read_status_payload",
        lambda self, _run_dir: {"status": "waiting_user"},
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._latest_attempt_number",
        lambda self, _run_dir: 1,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        AsyncMock(return_value={"interaction_id": 7, "kind": "open_text", "prompt": "请继续输入"}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_auth",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "codex", "runtime_options": {"execution_mode": "interactive"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=1200),
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-wait-drain",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "assistant.message.final" for evt in chat_events)
    assert any(evt["type"] == "user.input.required" for evt in chat_events)


@pytest.mark.asyncio
async def test_drain_trailing_chat_events_waits_for_expected_attempt(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-terminal-drain"
    (run_dir / ".audit").mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "succeeded")

    available_attempts = [3, 3, 4, 4]

    def _latest_attempt_number(self, _run_dir: Path) -> int:
        _ = self
        if available_attempts:
            return available_attempts.pop(0)
        return 4

    call_counter = {"count": 0}

    async def _list_event_history(self, **kwargs):
        _ = self
        call_counter["count"] += 1
        from_seq = kwargs.get("from_seq")
        if from_seq == 1 and call_counter["count"] >= 3:
            return [
                {
                    "seq": 1,
                    "type": "assistant.message.final",
                    "data": {"message_id": "m_4_1", "text": "terminal message"},
                    "meta": {"attempt": 4},
                }
            ]
        return []

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService._latest_attempt_number",
        _latest_attempt_number,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.RunObservabilityService.list_event_history",
        _list_event_history,
    )

    service = RunObservabilityService()
    drained, last_seq = await service._drain_trailing_chat_events(
        run_dir=run_dir,
        request_id="req-terminal-drain",
        last_chat_event_seq=0,
        poll_interval_sec=0.01,
        expected_attempt=4,
        drain_window_sec=0.5,
    )

    assert last_seq == 1
    assert any(evt["type"] == "assistant.message.final" for evt in drained)
    assert call_counter["count"] >= 3


@pytest.mark.asyncio
async def test_iter_sse_events_waiting_auth_chat_only(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-auth-wait"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="opencode",
                type_name="auth.required",
                data={
                    "auth_session_id": "auth-1",
                    "engine": "opencode",
                    "provider_id": "google",
                    "challenge_kind": "api_key",
                    "phase": "challenge_active",
                    "prompt": "API key is required.",
                    "instructions": "Paste API key into chat.",
                    "accepts_chat_input": True,
                    "input_kind": "api_key",
                    "source_attempt": 1,
                },
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=2,
                engine="opencode",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="running",
                    target_state="waiting_auth",
                    trigger="auth.required",
                    updated_at="2026-03-10T00:00:01Z",
                    pending_interaction_id=None,
                    pending_auth_session_id="auth-1",
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "waiting_auth")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_auth",
        AsyncMock(
            return_value={
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "challenge_kind": "api_key",
                "prompt": "API key is required.",
                "auth_url": None,
                "user_code": None,
                "instructions": "Paste API key into chat.",
                "accepts_chat_input": True,
                "input_kind": "api_key",
                "last_error": None,
                "source_attempt": 1,
                "phase": "challenge_active",
            }
        ),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "opencode", "runtime_options": {"execution_mode": "interactive"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=1200),
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-auth",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    assert events[0]["event"] == "snapshot"
    assert events[0]["data"]["pending_auth_session_id"] == "auth-1"
    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "auth.required" for evt in chat_events)
    assert any(
        evt["type"] == "conversation.state.changed" and evt["data"].get("to") == "waiting_auth"
        for evt in chat_events
    )


@pytest.mark.asyncio
async def test_iter_sse_events_cursor_skips_old_chat_events(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-cursor"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="codex",
                type_name="assistant.message.final",
                data={"message_id": "m-1", "text": "first"},
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=2,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="running",
                    target_state="succeeded",
                    trigger="turn.succeeded",
                    updated_at="2026-03-10T00:00:01Z",
                    pending_interaction_id=None,
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "succeeded")
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    first_pass = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cursor",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        first_pass.append(item)
    max_seq = max(
        evt["data"]["seq"]
        for evt in first_pass
        if evt["event"] == "chat_event"
    )

    second_pass = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cursor",
        cursor=max_seq,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        second_pass.append(item)
    second_chat_events = [evt for evt in second_pass if evt["event"] == "chat_event"]
    assert second_chat_events == []


@pytest.mark.asyncio
async def test_list_event_history_filters_fcmp_by_seq(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        audit_dir / "fcmp_events.1.jsonl",
        [
            make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="queued",
                    target_state="running",
                    trigger="turn.started",
                    updated_at="2026-03-10T00:00:00Z",
                    pending_interaction_id=None,
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=2,
                engine="codex",
                type_name="assistant.message.final",
                data={"message_id": "m-1", "text": "hello"},
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=3,
                engine="codex",
                type_name="diagnostic.warning",
                data={"code": "X"},
                attempt_number=1,
            ).model_dump(mode="json"),
            make_fcmp_event(
                run_id=run_dir.name,
                seq=4,
                engine="codex",
                type_name="conversation.state.changed",
                data=make_fcmp_state_changed(
                    source_state="running",
                    target_state="succeeded",
                    trigger="turn.succeeded",
                    updated_at="2026-03-10T00:00:01Z",
                    pending_interaction_id=None,
                ),
                attempt_number=1,
            ).model_dump(mode="json"),
        ],
    )
    write_jsonl(audit_dir / "events.1.jsonl", [])
    write_jsonl(audit_dir / "orchestrator_events.1.jsonl", [])
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "succeeded")
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    rows = await service.list_event_history(
        run_dir=run_dir,
        request_id="req-history",
        from_seq=2,
        to_seq=4,
    )
    assert rows
    assert all(2 <= row["seq"] <= 4 for row in rows)
    assert all(row["protocol_version"] == "fcmp/1.0" for row in rows)


@pytest.mark.asyncio
async def test_read_log_range_prefers_attempt_logs(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-range"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "succeeded")
    (audit_dir / "stdout.1.log").write_text("audit-stdout", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text(
        json.dumps({"completion": {"state": "completed", "reason_code": "DONE_MARKER_FOUND"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "codex", "runtime_options": {"execution_mode": "auto"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )

    service = RunObservabilityService()
    payload = await service.read_log_range(
        run_dir=run_dir,
        request_id="req-range",
        stream="stdout",
        byte_from=0,
        byte_to=5,
    )
    assert payload["chunk"] == "audit"


@pytest.mark.asyncio
async def test_read_log_range_does_not_fallback_to_legacy_logs(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-no-fallback"
    logs_dir = run_dir / "logs"
    audit_dir = run_dir / ".audit"
    logs_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("legacy-stdout", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text("{}", encoding="utf-8")
    _write_state_file(run_dir, "running")

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "codex", "runtime_options": {"execution_mode": "auto"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )

    service = RunObservabilityService()
    payload = await service.read_log_range(
        run_dir=run_dir,
        request_id="req-no-fallback",
        stream="stdout",
        byte_from=0,
        byte_to=64,
    )
    assert payload["chunk"] == ""


@pytest.mark.asyncio
async def test_materialize_protocol_stream_preserves_existing_fcmp_order(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-materialize-order"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_user")
    (audit_dir / "stdout.1.log").write_text("", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    (audit_dir / "orchestrator_events.1.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-03-04T00:00:00Z",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "interaction.user_input.required",
                "data": {"interaction_id": 7, "kind": "open_text"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / "meta.1.json").write_text(
        json.dumps(
            {
                "engine": "codex",
                "status": "waiting_user",
                "completion": {"state": "awaiting_user_input", "reason_code": "WAITING_USER_INPUT"},
            }
        ),
        encoding="utf-8",
    )

    existing_rows = [
        make_fcmp_event(
            run_id=run_dir.name,
            seq=1,
            engine="codex",
            type_name="user.input.required",
            data={
                "interaction_id": 7,
                "kind": "open_text",
                "prompt": "User input is required to continue.",
            },
            attempt_number=1,
        ).model_dump(mode="json"),
        make_fcmp_event(
            run_id=run_dir.name,
            seq=2,
            engine="codex",
            type_name="conversation.state.changed",
            data=make_fcmp_state_changed(
                source_state="running",
                target_state="waiting_user",
                trigger="turn.needs_input",
                updated_at="2026-03-04T00:00:00Z",
                pending_interaction_id=7,
                pending_owner="waiting_user",
            ),
            attempt_number=1,
        ).model_dump(mode="json"),
    ]
    write_jsonl(audit_dir / "fcmp_events.1.jsonl", existing_rows)

    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )

    service = RunObservabilityService()
    payload = await service._materialize_protocol_stream(
        run_dir=run_dir,
        request_id=None,
        status_payload={"status": "waiting_user"},
        attempt_number=1,
    )

    assert [row["type"] for row in payload["fcmp_events"]] == [
        "user.input.required",
        "conversation.state.changed",
    ]
    persisted_rows = [
        json.loads(line)
        for line in (audit_dir / "fcmp_events.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["type"] for row in persisted_rows] == [
        "user.input.required",
        "conversation.state.changed",
    ]


@pytest.mark.asyncio
async def test_rebuild_protocol_history_prefers_io_chunks_and_creates_backup(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-rebuild"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "succeeded")
    (audit_dir / "meta.1.json").write_text(
        json.dumps({"engine": "unknown", "status": "succeeded", "completion": {"state": "completed"}}),
        encoding="utf-8",
    )
    (audit_dir / "orchestrator_events.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "events.1.jsonl").write_text('{"legacy":"old"}\n', encoding="utf-8")
    (audit_dir / "fcmp_events.1.jsonl").write_text('{"legacy":"old"}\n', encoding="utf-8")
    (audit_dir / "parser_diagnostics.1.jsonl").write_text("", encoding="utf-8")
    (audit_dir / "protocol_metrics.1.json").write_text("{}", encoding="utf-8")
    (audit_dir / "io_chunks.1.jsonl").write_text(
        json.dumps(
            {
                "seq": 1,
                "ts": "2026-03-10T00:00:00Z",
                "stream": "stdout",
                "byte_from": 0,
                "byte_to": 6,
                "payload_b64": base64.b64encode(b"hello\n").decode("ascii"),
                "encoding": "base64",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_request",
        AsyncMock(return_value={"engine": "unknown", "runtime_options": {"execution_mode": "auto"}}),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )

    service = RunObservabilityService()
    strict_replay_mock = AsyncMock(
        return_value={
            "success": True,
            "written": True,
            "reason": "OK",
            "source": "io_chunks",
            "event_count": 3,
            "fcmp_count": 2,
            "diagnostics": [],
        }
    )
    monkeypatch.setattr(service, "_strict_replay_attempt", strict_replay_mock)
    payload = await service.rebuild_protocol_history(run_dir=run_dir, request_id="req-rebuild")

    assert payload["success"] is True
    assert payload["mode"] == "strict_replay"
    assert payload["attempts"][0]["source"] == "io_chunks"
    assert payload["attempts"][0]["written"] is True
    assert payload["attempts"][0]["reason"] == "OK"
    assert payload["attempts"][0]["mode"] == "strict_replay"
    strict_replay_mock.assert_awaited_once()
    backup_dir = Path(payload["backup_dir"]) / "attempt-1"
    assert (backup_dir / "events.1.jsonl").exists()
    assert (backup_dir / "fcmp_events.1.jsonl").exists()


@pytest.mark.asyncio
async def test_list_timeline_history_merges_protocol_chat_and_client(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-timeline"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    service = RunObservabilityService()

    async def _resolve_attempt_number(**_kwargs):
        return 2

    async def _list_protocol_history(**kwargs):
        stream = kwargs["stream"]
        attempt = kwargs["attempt"]
        assert kwargs["limit"] == 300
        if stream == "orchestrator" and attempt == 1:
            return {
                "attempt": 1,
                "available_attempts": [1, 2],
                "events": [{"seq": 1, "ts": "2026-03-06T10:00:00Z", "type": "attempt.started", "payload": {}}],
            }
        if stream == "rasp" and attempt == 1:
            return {
                "attempt": 1,
                "available_attempts": [1, 2],
                "events": [{"seq": 1, "type": "raw.stdout", "source": {"engine": "opencode", "parser": "stream"}}],
            }
        if stream == "fcmp" and attempt == 2:
            return {
                "attempt": 2,
                "available_attempts": [1, 2],
                "events": [
                    {
                        "seq": 5,
                        "ts": "2026-03-06T10:00:01Z",
                        "type": "interaction.reply.accepted",
                        "payload": {"response": {"text": "hello timeline"}},
                        "raw_ref": {"attempt_number": 2, "stream": "stdout", "byte_from": 0, "byte_to": 10},
                    }
                ],
            }
        return {"attempt": attempt, "available_attempts": [1, 2], "events": []}

    async def _get_chat_history_payload(**_kwargs):
        return {
            "events": [
                {
                    "seq": 7,
                    "created_at": "2026-03-06T10:00:02Z",
                    "role": "assistant",
                    "kind": "assistant_final",
                    "text": "assistant final",
                    "attempt": 2,
                },
                {
                    "seq": 8,
                    "created_at": "2026-03-06T10:00:03Z",
                    "role": "user",
                    "kind": "interaction_reply",
                    "text": "user reply",
                    "attempt": 2,
                },
            ],
            "cursor_floor": 1,
            "cursor_ceiling": 8,
            "source": "mixed",
        }

    monkeypatch.setattr(service, "_list_available_attempts", lambda _run_dir: [1, 2])
    monkeypatch.setattr(service, "_resolve_attempt_number", _resolve_attempt_number)
    monkeypatch.setattr(service, "list_protocol_history", _list_protocol_history)
    monkeypatch.setattr(service, "get_chat_history_payload", _get_chat_history_payload)

    payload = await service.list_timeline_history(
        run_dir=run_dir,
        request_id="req-timeline",
        cursor=0,
        limit=100,
    )
    events = payload["events"]
    lanes = [event["lane"] for event in events]
    assert lanes[0] == "orchestrator"
    assert "parser_rasp" in lanes
    assert "protocol_fcmp" in lanes
    assert "chat_history" in lanes
    assert "client" in lanes
    assert any(event["kind"] == "interaction.reply.accepted" and event["lane"] == "client" for event in events)
    assert payload["cursor_ceiling"] >= len(events)

    last_cursor = payload["cursor_ceiling"]
    incremental = await service.list_timeline_history(
        run_dir=run_dir,
        request_id="req-timeline",
        cursor=last_cursor,
        limit=100,
    )
    assert incremental["events"] == []


@pytest.mark.asyncio
async def test_list_timeline_history_reuses_cache_when_audit_signature_unchanged(
    monkeypatch, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run-timeline-cache"
    (run_dir / ".audit").mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "running")
    service = RunObservabilityService()
    calls = {"count": 0}

    async def _resolve_attempt_number(**_kwargs):
        return 1

    async def _list_protocol_history(**kwargs):
        calls["count"] += 1
        stream = kwargs["stream"]
        return {
            "attempt": 1,
            "available_attempts": [1],
            "events": [{"seq": 1, "ts": "2026-03-06T10:00:00Z", "type": f"{stream}.event"}],
        }

    async def _get_chat_history_payload(**_kwargs):
        return {"events": [], "cursor_floor": 0, "cursor_ceiling": 0, "source": "audit"}

    monkeypatch.setattr(service, "_list_available_attempts", lambda _run_dir: [1])
    monkeypatch.setattr(service, "_resolve_attempt_number", _resolve_attempt_number)
    monkeypatch.setattr(service, "list_protocol_history", _list_protocol_history)
    monkeypatch.setattr(service, "get_chat_history_payload", _get_chat_history_payload)

    first = await service.list_timeline_history(run_dir=run_dir, request_id="req-cache", cursor=0, limit=100)
    assert calls["count"] == 3
    second = await service.list_timeline_history(run_dir=run_dir, request_id="req-cache", cursor=0, limit=100)
    assert calls["count"] == 3
    assert first["events"] == second["events"]
    assert second["source"] == "cached"
