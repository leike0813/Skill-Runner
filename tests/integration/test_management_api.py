from pathlib import Path
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.models import SkillManifest


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_management_api_end_to_end_connectivity(monkeypatch, tmp_path: Path):
    skill_dir = tmp_path / "skills" / "demo-skill"
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets" / "runner.json").write_text("{}", encoding="utf-8")
    (skill_dir / "assets" / "output.schema.json").write_text("{}", encoding="utf-8")
    manifest = SkillManifest(
        id="demo-skill",
        name="Demo Skill",
        version="1.0.0",
        engines=["gemini"],
        schemas={"output": "assets/output.schema.json"},
        path=skill_dir,
    )
    monkeypatch.setattr("server.routers.management.skill_registry.list_skills", lambda: [manifest])
    monkeypatch.setattr(
        "server.routers.management.skill_registry.get_skill",
        lambda skill_id: manifest if skill_id == "demo-skill" else None,
    )
    monkeypatch.setattr(
        "server.routers.management.list_skill_entries",
        lambda _path: [{"path": "SKILL.md", "is_dir": False}],
    )

    monkeypatch.setattr(
        "server.routers.management.model_registry.list_engines",
        lambda: [{"engine": "gemini", "cli_version_detected": "1.0.0"}],
    )
    monkeypatch.setattr(
        "server.routers.management.model_registry.get_models",
        lambda _engine: SimpleNamespace(
            cli_version_detected="1.0.0",
            models=[
                SimpleNamespace(
                    id="gemini-2.5-pro",
                    display_name="Gemini 2.5 Pro",
                    deprecated=False,
                    notes="snapshot",
                    supported_effort=None,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        "server.routers.management.agent_cli_manager.collect_auth_status",
        lambda: {"gemini": {"auth_ready": True}},
    )

    monkeypatch.setattr(
        "server.routers.management.run_observability_service.get_run_detail",
        lambda _request_id: {
            "request_id": "req-1",
            "run_id": "run-1",
            "run_dir": str(tmp_path / "runs" / "run-1"),
            "skill_id": "demo-skill",
            "engine": "gemini",
            "status": "succeeded",
            "updated_at": "2026-02-16T00:00:00",
            "poll_logs": False,
            "entries": [{"path": "logs/stdout.txt", "is_dir": False}],
        },
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.routers.management.run_store.get_interaction_count",
        lambda _request_id: 0,
    )

    skills_res = await _request("GET", "/v1/management/skills")
    assert skills_res.status_code == 200
    assert skills_res.json()["skills"][0]["id"] == "demo-skill"

    skill_detail_res = await _request("GET", "/v1/management/skills/demo-skill")
    assert skill_detail_res.status_code == 200
    assert skill_detail_res.json()["files"][0]["path"] == "SKILL.md"

    engines_res = await _request("GET", "/v1/management/engines")
    assert engines_res.status_code == 200
    assert engines_res.json()["engines"][0]["engine"] == "gemini"

    run_res = await _request("GET", "/v1/management/runs/req-1")
    assert run_res.status_code == 200
    assert run_res.json()["status"] == "succeeded"
