import json
from pathlib import Path
from types import SimpleNamespace

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


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


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
        lambda: [{"engine": "codex", "cli_version_detected": "0.90.0"}],
    )
    monkeypatch.setattr(
        "server.routers.management.agent_cli_manager.collect_auth_status",
        lambda: {
            "codex": {"auth_ready": True},
        },
    )
    monkeypatch.setattr(
        "server.routers.management.model_registry.get_models",
        lambda _engine: SimpleNamespace(
            cli_version_detected="0.90.0",
            models=[
                SimpleNamespace(
                    id="gpt-5.2-codex",
                    display_name="GPT-5.2 Codex",
                    deprecated=False,
                    notes="snapshot",
                    supported_effort=["low", "high"],
                )
            ],
        ),
    )

    list_res = await _request("GET", "/v1/management/engines")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["engines"][0]["engine"] == "codex"
    assert body["engines"][0]["auth_ready"] is True
    assert body["engines"][0]["models_count"] == 1

    detail_res = await _request("GET", "/v1/management/engines/codex")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["engine"] == "codex"
    assert detail["models"][0]["id"] == "gpt-5.2-codex"
    assert "upgrade_status" in detail


@pytest.mark.asyncio
async def test_management_run_state_includes_pending_and_interaction_count(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "waiting_user",
                "updated_at": "2026-02-16T00:00:00",
                "error": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.get_run_detail",
        lambda _request_id: {
            "request_id": "req-1",
            "run_id": "run-1",
            "run_dir": str(run_dir),
            "skill_id": "demo",
            "engine": "gemini",
            "status": "waiting_user",
            "updated_at": "2026-02-16T00:00:00",
            "poll_logs": False,
            "recovery_state": "recovered_waiting",
            "recovered_at": "2026-02-16T00:01:00",
            "recovery_reason": "resumable_waiting_preserved",
            "entries": [],
        },
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_pending_interaction",
        lambda _request_id: {"interaction_id": 9, "prompt": "x"},
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_interaction_count",
        lambda _request_id: 3,
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_auto_decision_stats",
        lambda _request_id: {
            "auto_decision_count": 2,
            "last_auto_decision_at": "2026-02-16T00:10:00",
        },
    )

    response = await _request("GET", "/v1/management/runs/req-1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting_user"
    assert body["pending_interaction_id"] == 9
    assert body["interaction_count"] == 3
    assert body["auto_decision_count"] == 2
    assert body["last_auto_decision_at"] == "2026-02-16T00:10:00"
    assert body["recovery_state"] == "recovered_waiting"
    assert body["recovered_at"] == "2026-02-16T00:01:00"
    assert body["recovery_reason"] == "resumable_waiting_preserved"


@pytest.mark.asyncio
async def test_management_run_files_and_preview(monkeypatch):
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.get_run_detail",
        lambda _request_id: {
            "request_id": "req-2",
            "run_id": "run-2",
            "run_dir": "/tmp/run-2",
            "skill_id": "demo",
            "engine": "gemini",
            "status": "running",
            "updated_at": "2026-02-16T00:00:00",
            "poll_logs": True,
            "entries": [{"path": "artifacts/out.txt", "is_dir": False}],
        },
    )
    monkeypatch.setattr(
        "server.routers.management.run_observability_service.build_run_file_preview",
        lambda _request_id, _path: {"type": "text", "content": "ok"},
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_interaction_count",
        lambda _request_id: 0,
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
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("hello", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-02-16T00:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-events"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )

    response = await _request("GET", "/v1/management/runs/req-events/events")
    assert response.status_code == 200
    assert "event: snapshot" in response.text
    assert "event: end" in response.text
    assert "\"reason\": \"terminal\"" in response.text


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
