from types import SimpleNamespace
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def _build_skill_dir(base: Path) -> Path:
    skill_dir = base / "demo-ui-skill"
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (skill_dir / "assets" / "runner.json").write_text('{"id":"demo-ui-skill"}', encoding="utf-8")
    (skill_dir / "assets" / "binary.bin").write_bytes(b"\x00\x01\x02")
    (skill_dir / "assets" / "large.txt").write_text("a" * (300 * 1024), encoding="utf-8")
    return skill_dir


@pytest.mark.asyncio
async def test_ui_index_available_when_auth_disabled(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)

    response = await _request("GET", "/ui")
    assert response.status_code == 200
    assert "Skill Runner 管理界面" in response.text


@pytest.mark.asyncio
async def test_ui_auth_protects_ui_and_skill_package_routes(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: True)
    monkeypatch.setattr(
        "server.services.ui_auth.get_ui_basic_auth_credentials",
        lambda: ("admin", "secret"),
    )
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_package_manager.create_install_request",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_package_manager.run_install",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "server.routers.engines.engine_upgrade_manager.create_task",
        lambda *_args, **_kwargs: "upgrade-1",
    )
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_manifest_view",
        lambda _engine: {
            "engine": "codex",
            "cli_version_detected": "0.89.0",
            "manifest": {"engine": "codex", "snapshots": []},
            "resolved_snapshot_version": "0.89.0",
            "resolved_snapshot_file": "models_0.89.0.json",
            "fallback_reason": None,
            "models": [],
        },
    )
    monkeypatch.setattr(
        "server.routers.engines.agent_cli_manager.collect_auth_status",
        lambda: {
            "codex": {
                "managed_present": True,
                "managed_cli_path": "/tmp/codex",
                "global_available": False,
                "global_cli_path": None,
                "effective_cli_path": "/tmp/codex",
                "effective_path_source": "managed",
                "credential_files": {"auth.json": True},
                "auth_ready": True,
            }
        },
    )

    response = await _request("GET", "/ui")
    assert response.status_code == 401

    response = await _request("GET", "/ui", auth=("admin", "secret"))
    assert response.status_code == 200

    response = await _request(
        "POST",
        "/v1/skill-packages/install",
        files={"file": ("skill.zip", b"zip-bytes", "application/zip")},
    )
    assert response.status_code == 401

    response = await _request(
        "POST",
        "/v1/skill-packages/install",
        auth=("admin", "secret"),
        files={"file": ("skill.zip", b"zip-bytes", "application/zip")},
    )
    assert response.status_code == 200

    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "all"})
    assert response.status_code == 401
    response = await _request(
        "POST",
        "/v1/engines/upgrades",
        auth=("admin", "secret"),
        json={"mode": "all"},
    )
    assert response.status_code == 200

    response = await _request("GET", "/v1/engines/codex/models/manifest")
    assert response.status_code == 401
    response = await _request("GET", "/v1/engines/codex/models/manifest", auth=("admin", "secret"))
    assert response.status_code == 200
    response = await _request("GET", "/v1/engines/auth-status")
    assert response.status_code == 401
    response = await _request("GET", "/v1/engines/auth-status", auth=("admin", "secret"))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ui_skills_table_highlight(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.skill_registry.list_skills",
        lambda: [
            SimpleNamespace(
                id="skill-a",
                name="Skill A",
                description="A desc",
                version="1.0.0",
                engines=["gemini"],
            ),
            SimpleNamespace(
                id="skill-b",
                name="Skill B",
                description="B desc",
                version="1.1.0",
                engines=["codex"],
            ),
        ],
    )

    response = await _request("GET", "/ui/skills/table?highlight_skill_id=skill-b")
    assert response.status_code == 200
    assert "Skill B" in response.text
    assert "background:#ecfdf5;" in response.text


@pytest.mark.asyncio
async def test_ui_install_status_succeeded_refreshes_table(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.skill_install_store.get_install",
        lambda _request_id: {
            "status": "succeeded",
            "skill_id": "demo-uploaded",
            "error": None,
        },
    )

    response = await _request("GET", "/ui/skill-packages/req-1/status")
    assert response.status_code == 200
    assert "安装成功：demo-uploaded" in response.text
    assert "/ui/skills/table?highlight_skill_id=demo-uploaded" in response.text
    assert "every 1s" not in response.text


@pytest.mark.asyncio
async def test_ui_skill_detail_and_text_preview(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    skill_dir = _build_skill_dir(tmp_path)
    monkeypatch.setattr(
        "server.routers.ui.skill_registry.get_skill",
        lambda _skill_id: SimpleNamespace(
            id="demo-ui-skill",
            name="Demo UI Skill",
            description="desc",
            version="1.0.0",
            engines=["gemini"],
            path=skill_dir,
        ),
    )

    detail_res = await _request("GET", "/ui/skills/demo-ui-skill")
    assert detail_res.status_code == 200
    assert "Package Structure" in detail_res.text
    assert "SKILL.md" in detail_res.text

    preview_res = await _request("GET", "/ui/skills/demo-ui-skill/view?path=SKILL.md")
    assert preview_res.status_code == 200
    assert "# skill" in preview_res.text


@pytest.mark.asyncio
async def test_ui_skill_preview_binary_and_large_and_invalid_path(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    skill_dir = _build_skill_dir(tmp_path)
    monkeypatch.setattr(
        "server.routers.ui.skill_registry.get_skill",
        lambda _skill_id: SimpleNamespace(
            id="demo-ui-skill",
            name="Demo UI Skill",
            description="desc",
            version="1.0.0",
            engines=["gemini"],
            path=skill_dir,
        ),
    )

    binary_res = await _request("GET", "/ui/skills/demo-ui-skill/view?path=assets/binary.bin")
    assert binary_res.status_code == 200
    assert "不可预览" in binary_res.text
    assert "无信息" in binary_res.text

    large_res = await _request("GET", "/ui/skills/demo-ui-skill/view?path=assets/large.txt")
    assert large_res.status_code == 200
    assert "文件过大不可预览" in large_res.text

    bad_path_res = await _request("GET", "/ui/skills/demo-ui-skill/view?path=../../etc/passwd")
    assert bad_path_res.status_code == 400


@pytest.mark.asyncio
async def test_ui_engines_page(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.model_registry.list_engines",
        lambda: [{"engine": "codex", "cli_version_detected": "0.89.0"}],
    )

    response = await _request("GET", "/ui/engines")
    assert response.status_code == 200
    assert "Engine 管理" in response.text
    assert "正在检测 Engine 版本与状态，请稍候..." in response.text
    assert 'hx-get="/ui/engines/table"' in response.text


@pytest.mark.asyncio
async def test_ui_engines_table_partial(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.model_registry.list_engines",
        lambda: [{"engine": "codex", "cli_version_detected": "0.89.0"}],
    )
    monkeypatch.setattr(
        "server.routers.ui.agent_cli_manager.collect_auth_status",
        lambda: {
            "codex": {
                "managed_present": True,
                "managed_cli_path": "/tmp/codex",
                "global_available": False,
                "global_cli_path": None,
                "effective_cli_path": "/tmp/codex",
                "effective_path_source": "managed",
                "credential_files": {"auth.json": True},
                "auth_ready": True,
            }
        },
    )

    response = await _request("GET", "/ui/engines/table")
    assert response.status_code == 200
    assert "codex" in response.text
    assert "/ui/engines/codex/models" in response.text
    assert "managed" in response.text
    assert "auth.json: ok" in response.text


@pytest.mark.asyncio
async def test_ui_engine_upgrade_status_partial(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.engine_upgrade_manager.get_task",
        lambda _request_id: {
            "status": "running",
            "results": {
                "gemini": {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}
            },
        },
    )

    response = await _request("GET", "/ui/engines/upgrades/req-1/status")
    assert response.status_code == 200
    assert "Request ID:" in response.text
    assert "gemini" in response.text
    assert "stdout" in response.text


@pytest.mark.asyncio
async def test_ui_engine_models_page(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.model_registry.get_manifest_view",
        lambda _engine: {
            "engine": "codex",
            "cli_version_detected": "0.89.0",
            "manifest": {"engine": "codex", "snapshots": []},
            "resolved_snapshot_version": "0.89.0",
            "resolved_snapshot_file": "models_0.89.0.json",
            "fallback_reason": None,
            "models": [{"id": "gpt-5.2-codex", "display_name": "GPT-5.2 Codex", "deprecated": False}],
        },
    )

    response = await _request("GET", "/ui/engines/codex/models")
    assert response.status_code == 200
    assert "模型管理：codex" in response.text
    assert "gpt-5.2-codex" in response.text


@pytest.mark.asyncio
async def test_ui_engine_models_add_snapshot_redirect(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.model_registry.add_snapshot_for_detected_version",
        lambda _engine, _models: None,
    )

    response = await _request(
        "POST",
        "/ui/engines/codex/models/snapshots",
        data={
            "id": ["gpt-5.2-codex"],
            "display_name": ["GPT-5.2 Codex"],
            "deprecated": ["false"],
            "notes": ["snapshot"],
            "supported_effort": ["low,high"],
        },
    )
    assert response.status_code == 303
    assert "/ui/engines/codex/models?message=Snapshot+created" in response.headers["location"]


@pytest.mark.asyncio
async def test_ui_runs_page_and_table(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.run_observability_service.list_runs",
        lambda limit=200: [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo-skill",
                "engine": "gemini",
                "status": "running",
                "updated_at": "2026-01-01T00:00:00",
                "file_state": {},
            }
        ],
    )

    response = await _request("GET", "/ui/runs")
    assert response.status_code == 200
    assert "Run 观测" in response.text

    table_res = await _request("GET", "/ui/runs/table")
    assert table_res.status_code == 200
    assert "req-1" in table_res.text
    assert "/ui/runs/req-1" in table_res.text


@pytest.mark.asyncio
async def test_ui_run_detail_preview_and_logs(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.run_observability_service.get_run_detail",
        lambda _request_id: {
            "request_id": "req-1",
            "run_id": "run-1",
            "run_dir": "/tmp/run-1",
            "skill_id": "demo-skill",
            "engine": "gemini",
            "status": "running",
            "updated_at": "2026-01-01T00:00:00",
            "entries": [{"rel_path": "logs/stdout.txt", "name": "stdout.txt", "is_dir": False, "depth": 1}],
            "file_state": {"stdout": {"exists": True, "is_dir": False, "size": 3, "mtime": "2026-01-01T00:00:00"}},
            "poll_logs": True,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.run_observability_service.build_run_file_preview",
        lambda _request_id, _path: {"mode": "text", "content": "ok", "size": 2, "meta": "2 bytes"},
    )
    monkeypatch.setattr(
        "server.routers.ui.run_observability_service.get_logs_tail",
        lambda _request_id: {
            "request_id": "req-1",
            "run_id": "run-1",
            "status": "running",
            "poll": True,
            "stdout": "stream-out",
            "stderr": "stream-err",
        },
    )

    detail_res = await _request("GET", "/ui/runs/req-1")
    assert detail_res.status_code == 200
    assert "Request: req-1" in detail_res.text
    assert "Run File Tree (Read-only)" in detail_res.text

    preview_res = await _request("GET", "/ui/runs/req-1/view?path=logs/stdout.txt")
    assert preview_res.status_code == 200
    assert "ok" in preview_res.text

    logs_res = await _request("GET", "/ui/runs/req-1/logs/tail")
    assert logs_res.status_code == 200
    assert "stream-out" in logs_res.text
    assert "every 2s" in logs_res.text
