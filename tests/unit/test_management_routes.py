import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.models import (
    CancelResponse,
    InteractionPendingResponse,
    InteractionReplyResponse,
    PendingInteraction,
    RunStatus,
    SkillManifest,
)
from server.services.platform.data_reset_service import DATA_RESET_CONFIRMATION_TEXT


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _write_state_file(run_dir: Path, status: str) -> None:
    state_dir = run_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "request_id": f"req-{run_dir.name}",
                "run_id": run_dir.name,
                "status": status,
                "updated_at": "2026-02-16T00:00:00",
                "current_attempt": 1,
                "state_phase": {
                    "waiting_auth_phase": None,
                    "dispatch_phase": None,
                },
                "pending": {
                    "owner": None,
                    "interaction_id": None,
                    "auth_session_id": None,
                    "payload": None,
                },
                "resume": {
                    "resume_ticket_id": None,
                    "resume_cause": None,
                    "source_attempt": None,
                    "target_attempt": None,
                },
                "runtime": {
                    "conversation_mode": "session",
                    "requested_execution_mode": None,
                    "effective_execution_mode": None,
                    "effective_interactive_require_user_reply": None,
                    "effective_interactive_reply_timeout_sec": None,
                    "effective_session_timeout_sec": None,
                },
                "error": None,
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_management_skills_list_and_detail(monkeypatch, tmp_path: Path):
    skill_dir = tmp_path / "demo-skill"
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets" / "runner.json").write_text("{}", encoding="utf-8")
    (skill_dir / "assets" / "output.schema.json").write_text("{}", encoding="utf-8")
    manifest = SkillManifest(
        id="demo-skill",
        name="Demo Skill",
        version="1.2.3",
        engines=["gemini", "codex"],
        unsupported_engines=["codex"],
        effective_engines=["gemini"],
        execution_modes=["auto", "interactive"],
        schemas={"output": "assets/output.schema.json"},
        entrypoint={"type": "prompt"},
        path=skill_dir,
    )
    monkeypatch.setattr(
        "server.routers.management.skill_registry.list_skills",
        lambda: [manifest],
    )
    monkeypatch.setattr(
        "server.routers.management.skill_registry.get_skill",
        lambda skill_id: manifest if skill_id == "demo-skill" else None,
    )
    monkeypatch.setattr(
        "server.routers.management.list_skill_entries",
        lambda _root: [{"path": "SKILL.md", "is_dir": False}],
    )

    list_res = await _request("GET", "/v1/management/skills")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["skills"][0]["id"] == "demo-skill"
    assert body["skills"][0]["health"] == "healthy"
    assert body["skills"][0]["execution_modes"] == ["auto", "interactive"]
    assert body["skills"][0]["engines"] == ["gemini", "codex"]
    assert body["skills"][0]["unsupported_engines"] == ["codex"]
    assert body["skills"][0]["effective_engines"] == ["gemini"]

    detail_res = await _request("GET", "/v1/management/skills/demo-skill")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == "demo-skill"
    assert detail["schemas"]["output"] == "assets/output.schema.json"
    assert detail["entrypoints"]["type"] == "prompt"
    assert detail["files"][0]["path"] == "SKILL.md"
    assert detail["execution_modes"] == ["auto", "interactive"]
    assert detail["effective_engines"] == ["gemini"]


@pytest.mark.asyncio
async def test_management_skill_schemas_endpoint(monkeypatch, tmp_path: Path):
    skill_dir = tmp_path / "schema-skill"
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets" / "runner.json").write_text("{}", encoding="utf-8")
    (skill_dir / "assets" / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"query": {"type": "string"}}}),
        encoding="utf-8",
    )
    (skill_dir / "assets" / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"top_k": {"type": "integer"}}}),
        encoding="utf-8",
    )
    (skill_dir / "assets" / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"answer": {"type": "string"}}}),
        encoding="utf-8",
    )
    manifest = SkillManifest(
        id="schema-skill",
        name="Schema Skill",
        version="1.0.0",
        engines=["gemini"],
        schemas={
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        path=skill_dir,
    )
    monkeypatch.setattr(
        "server.routers.management.skill_registry.get_skill",
        lambda skill_id: manifest if skill_id == "schema-skill" else None,
    )

    res = await _request("GET", "/v1/management/skills/schema-skill/schemas")
    assert res.status_code == 200
    body = res.json()
    assert body["skill_id"] == "schema-skill"
    assert body["input"]["type"] == "object"
    assert body["parameter"]["properties"]["top_k"]["type"] == "integer"
    assert body["output"]["properties"]["answer"]["type"] == "string"

    missing = await _request("GET", "/v1/management/skills/missing/schemas")
    assert missing.status_code == 404
    assert "Skill not found" in missing.text
    assert str(tmp_path) not in missing.text


@pytest.mark.asyncio
async def test_management_engines_list_and_detail(monkeypatch):
    monkeypatch.setattr(
        "server.routers.management.model_registry.list_engines",
        lambda: [
            {"engine": "codex", "cli_version_detected": "0.90.0"},
            {"engine": "opencode", "cli_version_detected": "0.1.0"},
        ],
    )
    monkeypatch.setattr(
        "server.routers.management.model_registry.get_models",
        lambda engine: (
            SimpleNamespace(
                cli_version_detected="0.1.0",
                models=[
                    SimpleNamespace(
                        id="openai/gpt-5",
                        display_name="OpenAI GPT-5",
                        deprecated=False,
                        notes="runtime_probe_cache",
                        supported_effort=None,
                        provider="openai",
                        model="gpt-5",
                    )
                ],
            )
            if engine == "opencode"
            else SimpleNamespace(
                cli_version_detected="0.90.0",
                models=[
                    SimpleNamespace(
                        id="gpt-5.2-codex",
                        display_name="GPT-5.2 Codex",
                        deprecated=False,
                        notes="snapshot",
                        supported_effort=["low", "high"],
                        provider=None,
                        model=None,
                    )
                ],
            )
        ),
    )

    list_res = await _request("GET", "/v1/management/engines")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["engines"][0]["engine"] == "codex"
    assert body["engines"][0]["models_count"] == 1
    assert "auth_ready" not in body["engines"][0]
    assert "sandbox_status" not in body["engines"][0]

    detail_res = await _request("GET", "/v1/management/engines/codex")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["engine"] == "codex"
    assert detail["models"][0]["id"] == "gpt-5.2-codex"
    assert "upgrade_status" in detail
    assert "auth_ready" not in detail
    assert "sandbox_status" not in detail

    opencode_detail_res = await _request("GET", "/v1/management/engines/opencode")
    assert opencode_detail_res.status_code == 200
    opencode_detail = opencode_detail_res.json()
    assert opencode_detail["models"][0]["provider"] == "openai"
    assert opencode_detail["models"][0]["model"] == "gpt-5"


@pytest.mark.asyncio
async def test_management_engine_auth_import_spec_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.management.auth_import_service.get_import_spec",
        lambda **_kwargs: {
            "engine": "gemini",
            "provider_id": None,
            "supported": True,
            "ask_user": {
                "kind": "upload_files",
                "prompt": "Upload credential files to complete authentication.",
                "hint": "Select required files and submit to continue.",
                "files": [
                    {
                        "name": "google_accounts.json",
                        "required": True,
                        "hint": "$HOME/.gemini/google_accounts.json",
                        "accept": ".json",
                    },
                    {
                        "name": "oauth_creds.json",
                        "required": True,
                        "hint": "$HOME/.gemini/oauth_creds.json",
                        "accept": ".json",
                    },
                ],
                "ui_hints": {"risk_notice_required": False},
            },
        },
    )
    response = await _request("GET", "/v1/management/engines/gemini/auth/import/spec")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "gemini"
    assert body["supported"] is True
    assert body["ask_user"]["kind"] == "upload_files"
    assert [item["name"] for item in body["ask_user"]["files"]] == [
        "google_accounts.json",
        "oauth_creds.json",
    ]


@pytest.mark.asyncio
async def test_management_engine_auth_import_submit_route(monkeypatch):
    submitted = AsyncMock()
    submitted.return_value = {
        "engine": "opencode",
        "provider_id": "google",
        "imported_files": [
            {
                "source": "auth.json",
                "target_relpath": ".local/share/opencode/auth.json",
                "target_path": "/tmp/auth.json",
                "required": True,
            }
        ],
        "risk_notice_required": True,
    }
    monkeypatch.setattr(
        "server.routers.management.auth_import_service.import_auth_files",
        lambda **_kwargs: submitted.return_value,
    )
    response = await _request(
        "POST",
        "/v1/management/engines/opencode/auth/import",
        data={"provider_id": "google"},
        files=[("files", ("auth.json", b"{}", "application/json"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "opencode"
    assert body["provider_id"] == "google"
    assert body["imported_files"][0]["source"] == "auth.json"


@pytest.mark.asyncio
async def test_management_run_state_includes_pending_and_interaction_count(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_state_file(run_dir, "waiting_user")
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.get_run_detail",
        AsyncMock(return_value={
            "request_id": "req-1",
            "run_id": "run-1",
            "run_dir": str(run_dir),
            "skill_id": "demo",
            "engine": "gemini",
            "status": "waiting_user",
            "updated_at": "2026-02-16T00:00:00",
            "poll_logs": False,
            "interactive_auto_reply": True,
            "interactive_reply_timeout_sec": 5,
            "recovery_state": "recovered_waiting",
            "recovered_at": "2026-02-16T00:01:00",
            "recovery_reason": "resumable_waiting_preserved",
            "entries": [],
        }),
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_pending_interaction",
        AsyncMock(return_value={"interaction_id": 9, "prompt": "x"}),
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_interaction_count",
        AsyncMock(return_value=3),
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_auto_decision_stats",
        AsyncMock(return_value={
            "auto_decision_count": 2,
            "last_auto_decision_at": "2026-02-16T00:10:00",
        }),
    )

    response = await _request("GET", "/v1/management/runs/req-1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting_user"
    assert body["pending_interaction_id"] == 9
    assert body["interaction_count"] == 3
    assert body["auto_decision_count"] == 2
    assert body["last_auto_decision_at"] == "2026-02-16T00:10:00"
    assert body["interactive_auto_reply"] is True
    assert body["interactive_reply_timeout_sec"] == 5
    assert body["recovery_state"] == "recovered_waiting"
    assert body["recovered_at"] == "2026-02-16T00:01:00"
    assert body["recovery_reason"] == "resumable_waiting_preserved"


@pytest.mark.asyncio
async def test_management_run_files_and_preview(monkeypatch):
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.get_run_detail",
        AsyncMock(return_value={
            "request_id": "req-2",
            "run_id": "run-2",
            "run_dir": "/tmp/run-2",
            "skill_id": "demo",
            "engine": "gemini",
            "status": "running",
            "updated_at": "2026-02-16T00:00:00",
            "poll_logs": True,
            "entries": [{"path": "artifacts/out.txt", "is_dir": False}],
        }),
    )
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.build_run_file_preview",
        AsyncMock(return_value={"type": "text", "content": "ok"}),
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_pending_interaction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_interaction_count",
        AsyncMock(return_value=0),
    )

    files_res = await _request("GET", "/v1/management/runs/req-2/files")
    assert files_res.status_code == 200
    assert files_res.json()["entries"][0]["path"] == "artifacts/out.txt"

    preview_res = await _request("GET", "/v1/management/runs/req-2/file?path=artifacts/out.txt")
    assert preview_res.status_code == 200
    assert preview_res.json()["preview"]["content"] == "ok"


@pytest.mark.asyncio
async def test_management_run_events_stream(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-events"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "stdout.1.log").write_text("hello", encoding="utf-8")
    (audit_dir / "stderr.1.log").write_text("", encoding="utf-8")
    _write_state_file(run_dir, "succeeded")
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        AsyncMock(
            side_effect=lambda request_id: {
                "request_id": request_id,
                "run_id": "run-events",
                "engine": "gemini",
            }
        ),
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_pending_interaction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.list_interaction_history",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "server.runtime.observability.run_observability.run_store.get_effective_session_timeout",
        AsyncMock(return_value=None),
    )

    response = await _request("GET", "/v1/management/runs/req-events/events")
    assert response.status_code == 200
    assert "event: snapshot" in response.text
    # Strict audit-only mode: without attempt event logs, stream may still emit
    # diagnostics, but must not synthesize assistant/user conversation events.
    assert '"type": "assistant.message.final"' not in response.text
    assert '"type": "user.input.required"' not in response.text
    assert "event: end" not in response.text


@pytest.mark.asyncio
async def test_management_run_events_history_delegate(monkeypatch):
    async def _history(
        request_id: str,
        from_seq: int | None = None,
        to_seq: int | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ):
        assert request_id == "req-events"
        assert from_seq == 2
        assert to_seq == 4
        assert from_ts is None
        assert to_ts is None
        return {
            "request_id": request_id,
            "count": 1,
            "events": [{"seq": 3, "event": {"type": "agent.message.final"}}],
        }

    monkeypatch.setattr("server.routers.management.jobs_router.list_run_event_history", _history)

    response = await _request(
        "GET",
        "/v1/management/runs/req-events/events/history?from_seq=2&to_seq=4",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-events"
    assert payload["count"] == 1
    assert payload["events"][0]["seq"] == 3


@pytest.mark.asyncio
async def test_management_run_chat_history_delegate(monkeypatch):
    async def _history(
        request_id: str,
        from_seq: int | None = None,
        to_seq: int | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ):
        assert request_id == "req-chat"
        assert from_seq == 2
        assert to_seq == 4
        assert from_ts is None
        assert to_ts is None
        return {
            "request_id": request_id,
            "count": 2,
            "events": [
                {"seq": 3, "role": "user", "text": "API key submitted"},
                {"seq": 4, "role": "system", "text": "Authentication completed. Resuming task..."},
            ],
        }

    monkeypatch.setattr("server.routers.management.jobs_router.list_run_chat_history", _history)

    response = await _request(
        "GET",
        "/v1/management/runs/req-chat/chat/history?from_seq=2&to_seq=4",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-chat"
    assert payload["count"] == 2
    assert payload["events"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_management_run_log_range_delegate(monkeypatch):
    async def _logs_range(
        request_id: str,
        stream: str,
        byte_from: int,
        byte_to: int,
    ):
        assert request_id == "req-events"
        assert stream == "stderr"
        assert byte_from == 2
        assert byte_to == 7
        return {"stream": "stderr", "byte_from": 2, "byte_to": 7, "chunk": "error"}

    monkeypatch.setattr("server.routers.management.jobs_router.get_run_log_range", _logs_range)

    response = await _request(
        "GET",
        "/v1/management/runs/req-events/logs/range?stream=stderr&byte_from=2&byte_to=7",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stream"] == "stderr"
    assert payload["chunk"] == "error"


@pytest.mark.asyncio
async def test_management_run_protocol_rebuild_route(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-rebuild-route"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        AsyncMock(return_value={"request_id": "req-rebuild", "run_id": "run-rebuild-route"}),
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.rebuild_protocol_history",
        AsyncMock(
            return_value={
                "request_id": "req-rebuild",
                "run_id": "run-rebuild-route",
                "mode": "strict_replay",
                "success": True,
                "backup_dir": str(run_dir / ".audit" / "rebuild_backups" / "ts"),
                "attempts": [
                    {
                        "attempt": 1,
                        "mode": "strict_replay",
                        "source": "io_chunks",
                        "written": True,
                        "reason": "OK",
                        "success": True,
                    }
                ],
            }
        ),
    )

    response = await _request("POST", "/v1/management/runs/req-rebuild/protocol/rebuild")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["mode"] == "strict_replay"
    assert payload["attempts"][0]["mode"] == "strict_replay"
    assert payload["attempts"][0]["source"] == "io_chunks"


@pytest.mark.asyncio
async def test_management_run_pending_reply_cancel_delegate_to_jobs(monkeypatch):
    async def _pending(_request_id: str):
        return InteractionPendingResponse(
            request_id="req-3",
            status=RunStatus.WAITING_USER,
            pending=PendingInteraction(
                interaction_id=1,
                kind="open_text",
                prompt="continue?",
            ),
        )

    async def _reply(_request_id: str, _request, _background_tasks):
        return InteractionReplyResponse(
            request_id="req-3",
            status=RunStatus.QUEUED,
            accepted=True,
        )

    async def _cancel(_request_id: str):
        return CancelResponse(
            request_id="req-3",
            run_id="run-3",
            status=RunStatus.CANCELED,
            accepted=True,
            message="Cancel request accepted",
        )

    monkeypatch.setattr("server.routers.management.jobs_router.get_interaction_pending", _pending)
    monkeypatch.setattr("server.routers.management.jobs_router.reply_interaction", _reply)
    monkeypatch.setattr("server.routers.management.jobs_router.cancel_run", _cancel)

    pending = await _request("GET", "/v1/management/runs/req-3/pending")
    assert pending.status_code == 200
    assert pending.json()["pending"]["interaction_id"] == 1

    reply = await _request(
        "POST",
        "/v1/management/runs/req-3/reply",
        json={"interaction_id": 1, "response": {"ok": True}},
    )
    assert reply.status_code == 200
    assert reply.json()["accepted"] is True

    cancel = await _request("POST", "/v1/management/runs/req-3/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_management_reset_data_rejects_invalid_confirmation(monkeypatch):
    called = {"value": False}

    def _execute(_options):  # noqa: ANN001
        called["value"] = True
        raise AssertionError("execute_reset should not be called")

    monkeypatch.setattr("server.routers.management.data_reset_service.execute_reset", _execute)

    response = await _request(
        "POST",
        "/v1/management/system/reset-data",
        json={"confirmation": "WRONG"},
    )
    assert response.status_code == 400
    assert "confirmation must equal" in response.text
    assert called["value"] is False


@pytest.mark.asyncio
async def test_management_reset_data_dry_run(monkeypatch):
    captured = {}

    class _FakeResult:
        def to_payload(self):  # noqa: ANN201
            return {
                "dry_run": True,
                "data_dir": "/tmp/data",
                "db_files": ["/tmp/data/runs.db"],
                "data_dirs": ["/tmp/data/runs"],
                "optional_paths": ["/tmp/data/ui_shell_sessions"],
                "recreate_dirs": ["/tmp/data"],
                "targets": ["/tmp/data/runs.db", "/tmp/data/runs", "/tmp/data/ui_shell_sessions"],
                "deleted_count": 0,
                "missing_count": 0,
                "recreated_count": 0,
                "path_results": [],
            }

    def _execute(options):  # noqa: ANN001
        captured["options"] = options
        return _FakeResult()

    monkeypatch.setattr("server.routers.management.data_reset_service.execute_reset", _execute)

    response = await _request(
        "POST",
        "/v1/management/system/reset-data",
        json={
            "confirmation": DATA_RESET_CONFIRMATION_TEXT,
            "dry_run": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["deleted_count"] == 0
    assert body["missing_count"] == 0
    assert body["recreated_count"] == 0
    assert captured["options"].dry_run is True


@pytest.mark.asyncio
async def test_management_get_system_settings(monkeypatch):
    monkeypatch.setattr(
        "server.routers.management.get_logging_settings_payload",
        lambda: {
            "editable": {
                "level": "INFO",
                "format": "text",
                "retention_days": 7,
                "dir_max_bytes": 1024,
            },
            "read_only": {
                "dir": "/tmp/logs",
                "file_basename": "skill_runner.log",
                "rotation_when": "midnight",
                "rotation_interval": 1,
            },
        },
    )
    monkeypatch.setattr(
        "server.routers.management.config",
        SimpleNamespace(SYSTEM=SimpleNamespace(ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=False)),
    )

    response = await _request("GET", "/v1/management/system/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["logging"]["editable"]["level"] == "INFO"
    assert body["logging"]["read_only"]["dir"] == "/tmp/logs"
    assert body["engine_auth_session_log_persistence_enabled"] is False
    assert body["reset_confirmation_text"] == DATA_RESET_CONFIRMATION_TEXT


@pytest.mark.asyncio
async def test_management_query_system_logs(monkeypatch):
    captured = {}

    def _query(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return {
            "source": kwargs["source"],
            "items": [
                {
                    "ts": "2026-03-07T01:20:52Z",
                    "level": "ERROR",
                    "message": "Failed to install codex",
                    "raw": "2026-03-07 01:20:52 ERROR server.test: Failed to install codex",
                    "source": kwargs["source"],
                    "file": "skill_runner.log",
                    "line_no": 12,
                }
            ],
            "next_cursor": 1,
            "total_matched": 2,
        }

    monkeypatch.setattr("server.routers.management.system_log_explorer_service.query", _query)

    response = await _request(
        "GET",
        "/v1/management/system/logs/query?source=system&cursor=0&limit=200&level=error&q=install",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "system"
    assert payload["total_matched"] == 2
    assert payload["items"][0]["line_no"] == 12
    assert captured["level"] == "ERROR"


@pytest.mark.asyncio
async def test_management_query_system_logs_rejects_invalid_source():
    response = await _request(
        "GET",
        "/v1/management/system/logs/query?source=unknown",
    )
    assert response.status_code == 400
    assert "source must be one of" in response.text


@pytest.mark.asyncio
async def test_management_query_system_logs_rejects_invalid_level():
    response = await _request(
        "GET",
        "/v1/management/system/logs/query?source=system&level=TRACE",
    )
    assert response.status_code == 400
    assert "level must be one of" in response.text


@pytest.mark.asyncio
async def test_management_update_system_settings(monkeypatch):
    captured = {}

    def _update(payload):  # noqa: ANN001
        captured["payload"] = payload

    monkeypatch.setattr("server.routers.management.system_settings_service.update_logging_settings", _update)
    monkeypatch.setattr("server.routers.management.reload_logging_from_settings", lambda: None)
    monkeypatch.setattr(
        "server.routers.management.get_logging_settings_payload",
        lambda: {
            "editable": {
                "level": "DEBUG",
                "format": "json",
                "retention_days": 3,
                "dir_max_bytes": 2048,
            },
            "read_only": {
                "dir": "/tmp/logs",
                "file_basename": "skill_runner.log",
                "rotation_when": "midnight",
                "rotation_interval": 1,
            },
        },
    )

    response = await _request(
        "PUT",
        "/v1/management/system/settings",
        json={
            "logging": {
                "level": "DEBUG",
                "format": "json",
                "retention_days": 3,
                "dir_max_bytes": 2048,
            }
        },
    )
    assert response.status_code == 200
    assert captured["payload"]["level"] == "DEBUG"
    assert response.json()["logging"]["editable"]["format"] == "json"


@pytest.mark.asyncio
async def test_management_update_system_settings_rejects_invalid_payload():
    response = await _request(
        "PUT",
        "/v1/management/system/settings",
        json={
            "logging": {
                "level": "INFO",
                "format": "text",
                "retention_days": 1,
                "dir_max_bytes": 1,
                "rotation_when": "midnight",
            }
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_management_reset_data_execute_with_include_flags(monkeypatch):
    captured = {}

    class _FakeResult:
        def to_payload(self):  # noqa: ANN201
            return {
                "dry_run": False,
                "data_dir": "/tmp/data",
                "db_files": ["/tmp/data/runs.db"],
                "data_dirs": ["/tmp/data/runs"],
                "optional_paths": ["/tmp/data/logs", "/tmp/data/ui_shell_sessions"],
                "recreate_dirs": ["/tmp/data", "/tmp/data/runs"],
                "targets": ["/tmp/data/runs.db"],
                "deleted_count": 3,
                "missing_count": 1,
                "recreated_count": 2,
                "path_results": [{"path": "/tmp/data/runs.db", "status": "deleted"}],
            }

    def _execute(options):  # noqa: ANN001
        captured["options"] = options
        return _FakeResult()

    monkeypatch.setattr("server.routers.management.data_reset_service.execute_reset", _execute)
    monkeypatch.setattr(
        "server.routers.management.config",
        SimpleNamespace(SYSTEM=SimpleNamespace(ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=True)),
    )

    response = await _request(
        "POST",
        "/v1/management/system/reset-data",
        json={
            "confirmation": DATA_RESET_CONFIRMATION_TEXT,
            "dry_run": False,
            "include_logs": True,
            "include_engine_catalog": True,
            "include_engine_auth_sessions": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] == 3
    assert body["missing_count"] == 1
    assert body["recreated_count"] == 2
    assert captured["options"].include_logs is True
    assert captured["options"].include_engine_catalog is True
    assert captured["options"].include_engine_auth_sessions is True


@pytest.mark.asyncio
async def test_management_reset_data_normalizes_engine_auth_flag_when_feature_disabled(monkeypatch):
    captured = {}

    class _FakeResult:
        def to_payload(self):  # noqa: ANN201
            return {
                "dry_run": False,
                "data_dir": "/tmp/data",
                "db_files": [],
                "data_dirs": [],
                "optional_paths": [],
                "recreate_dirs": [],
                "targets": [],
                "deleted_count": 0,
                "missing_count": 0,
                "recreated_count": 0,
                "path_results": [],
            }

    def _execute(options):  # noqa: ANN001
        captured["options"] = options
        return _FakeResult()

    monkeypatch.setattr("server.routers.management.data_reset_service.execute_reset", _execute)
    monkeypatch.setattr(
        "server.routers.management.config",
        SimpleNamespace(SYSTEM=SimpleNamespace(ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=False)),
    )

    response = await _request(
        "POST",
        "/v1/management/system/reset-data",
        json={
            "confirmation": DATA_RESET_CONFIRMATION_TEXT,
            "include_engine_auth_sessions": True,
        },
    )
    assert response.status_code == 200
    assert captured["options"].include_engine_auth_sessions is False
