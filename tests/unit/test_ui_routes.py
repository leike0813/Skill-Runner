from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.services.engine_interaction_gate import EngineInteractionBusyError


async def _request(method: str, path: str, **kwargs):
    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)
    finally:
        app.router.lifespan_context = original_lifespan


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
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        lambda engine, method, auth_method=None, provider_id=None, transport=None, callback_base_url=None: {
            "session_id": "auth-1",
            "engine": engine,
            "method": method,
            "provider_id": provider_id,
            "status": "waiting_user",
            "auth_url": "https://auth.example.dev/device",
            "user_code": "TEST-1234",
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:01Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )

    response = await _request("GET", "/ui")
    assert response.status_code == 401

    response = await _request("GET", "/ui", auth=("admin", "secret"))
    assert response.status_code == 200

    response = await _request(
        "GET",
        "/v1/skill-packages/req-missing",
    )
    assert response.status_code == 401

    response = await _request(
        "GET",
        "/v1/skill-packages/req-missing",
        auth=("admin", "secret"),
    )
    assert response.status_code == 404

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
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "codex", "method": "auth"},
    )
    assert response.status_code == 401
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        auth=("admin", "secret"),
        json={"engine": "codex", "method": "auth"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ui_skills_table_highlight(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_skills",
        lambda: SimpleNamespace(
            skills=[
                SimpleNamespace(
                    id="skill-a",
                    name="Skill A",
                    version="1.0.0",
                    engines=["gemini"],
                    health="healthy",
                ),
                SimpleNamespace(
                    id="skill-b",
                    name="Skill B",
                    version="1.1.0",
                    engines=["codex"],
                    health="healthy",
                ),
            ]
        ),
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
    assert "/ui/management/skills/table?highlight_skill_id=demo-uploaded" in response.text
    assert "every 1s" not in response.text


@pytest.mark.asyncio
async def test_ui_skill_detail_and_text_preview(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    skill_dir = _build_skill_dir(tmp_path)
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_skill",
        lambda _skill_id: SimpleNamespace(
            id="demo-ui-skill",
            name="Demo UI Skill",
            description="desc",
            version="1.0.0",
            engines=["gemini"],
            files=[{"rel_path": "SKILL.md", "name": "SKILL.md", "is_dir": False, "depth": 0}],
        ),
    )
    monkeypatch.setattr(
        "server.routers.ui.skill_registry.get_skill",
        lambda _skill_id: SimpleNamespace(
            id="demo-ui-skill",
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
        "server.routers.ui.agent_cli_manager.profile",
        SimpleNamespace(data_dir=Path("/tmp/skill-runner"), managed_bin_dirs=[]),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_engines",
        lambda: SimpleNamespace(engines=[]),
    )
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.get_active_session_snapshot",
        lambda: {"active": False},
    )

    response = await _request("GET", "/ui/engines")
    assert response.status_code == 200
    assert "Engine 管理" in response.text
    assert "正在检测 Engine 版本与状态，请稍候..." in response.text
    assert 'hx-get="/ui/management/engines/table"' in response.text
    assert "内嵌终端（ttyd）" in response.text
    assert "Engine Auth（实验）" in response.text
    assert "Gemini OAuth代理（Callback）" in response.text
    assert "iFlow OAuth代理（Callback）" in response.text
    assert "iFlow OAuth代理（AuthCode/URL）" in response.text
    assert 'data-engine-auth-start="gemini"' in response.text
    assert 'data-engine-auth-start="iflow"' in response.text
    assert 'data-auth-method="callback"' in response.text
    assert "ttyd" in response.text


@pytest.mark.asyncio
async def test_ui_engine_auth_shell_route_is_removed(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)

    response = await _request("GET", "/ui/engines/auth-shell")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_ui_engine_tui_session_endpoints(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.ui_shell_manager.get_session_snapshot",
        lambda: {"active": True, "status": "running", "session_id": "s-1"},
    )
    monkeypatch.setattr(
        "server.routers.ui.ui_shell_manager.start_session",
        lambda engine: {"active": True, "status": "running", "session_id": "s-1", "engine": engine},
    )
    monkeypatch.setattr(
        "server.routers.ui.ui_shell_manager.stop_session",
        lambda: {"active": True, "status": "terminated", "session_id": "s-1"},
    )

    status_res = await _request("GET", "/ui/engines/tui/session")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "running"

    start_res = await _request("POST", "/ui/engines/tui/session/start", data={"engine": "codex"})
    assert start_res.status_code == 200
    assert start_res.json()["engine"] == "codex"

    input_res = await _request("POST", "/ui/engines/tui/session/input", data={"text": "hello"})
    assert input_res.status_code == 410

    resize_res = await _request("POST", "/ui/engines/tui/session/resize", data={"cols": "120", "rows": "40"})
    assert resize_res.status_code == 410

    stop_res = await _request("POST", "/ui/engines/tui/session/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "terminated"


@pytest.mark.asyncio
async def test_ui_engine_tui_start_busy_returns_409(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)

    from server.services.ui_shell_manager import UiShellBusyError

    def _raise_busy(_engine: str):
        raise UiShellBusyError("busy")

    monkeypatch.setattr("server.routers.ui.ui_shell_manager.start_session", _raise_busy)

    response = await _request("POST", "/ui/engines/tui/session/start", data={"engine": "codex"})
    assert response.status_code == 409
    assert response.json()["detail"] == "busy"


@pytest.mark.asyncio
async def test_ui_engine_tui_start_sandbox_probe_is_not_blocking(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.ui_shell_manager.start_session",
        lambda engine: {
            "active": True,
            "status": "running",
            "session_id": "s-2",
            "engine": engine,
            "sandbox_status": "unknown",
            "sandbox_message": "probe only",
        },
    )
    response = await _request("POST", "/ui/engines/tui/session/start", data={"engine": "gemini"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sandbox_status"] == "unknown"
    assert payload["engine"] == "gemini"


@pytest.mark.asyncio
async def test_ui_engines_table_partial(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_engines",
        lambda: SimpleNamespace(
            engines=[
                SimpleNamespace(
                    engine="codex",
                    cli_version="0.89.0",
                    auth_ready=True,
                    sandbox_status="available",
                    models_count=12,
                ),
                SimpleNamespace(
                    engine="iflow",
                    cli_version="1.2.3",
                    auth_ready=False,
                    sandbox_status="unsupported",
                    models_count=8,
                ),
            ]
        ),
    )

    response = await _request("GET", "/ui/engines/table")
    assert response.status_code == 200
    assert response.headers.get("Deprecation") == "true"
    assert "codex" in response.text
    assert "iflow" in response.text
    assert "/ui/engines/codex/models" in response.text
    assert "/ui/engines/iflow/models" in response.text
    assert "available" in response.text
    assert "yes" in response.text
    assert 'data-engine-start="codex"' in response.text
    assert 'data-engine-auth-start="codex"' in response.text
    assert 'data-auth-transport="oauth_proxy"' in response.text
    assert 'data-auth-transport="cli_delegate"' in response.text
    assert 'data-engine-auth-start="iflow"' in response.text


@pytest.mark.asyncio
async def test_ui_engine_auth_session_endpoints(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.start_session",
        lambda engine, method, auth_method=None, provider_id=None, transport=None, callback_base_url=None: {
            "session_id": "auth-1",
            "engine": engine,
            "method": method,
            "transport": transport or "oauth_proxy",
            "provider_id": provider_id,
            "status": "waiting_user",
            "auth_url": "https://auth.example.dev/device",
            "user_code": "TEST-1234",
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:01Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "method": "auth",
            "status": "waiting_user",
            "auth_url": "https://auth.example.dev/device",
            "user_code": "TEST-1234",
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:02Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.cancel_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "method": "auth",
            "status": "canceled",
            "auth_url": None,
            "user_code": None,
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:03Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": "Canceled by user",
            "exit_code": None,
            "terminal": True,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.input_session",
        lambda _session_id, _kind, _value: {
            "session_id": "auth-1",
            "engine": "gemini",
            "method": "auth",
            "status": "code_submitted_waiting_result",
            "input_kind": "code",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?foo=bar",
            "user_code": None,
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:02Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )

    start_res = await _request(
        "POST",
        "/ui/engines/auth/sessions",
        json={"engine": "codex", "method": "auth"},
    )
    assert start_res.status_code == 200
    assert start_res.json()["session_id"] == "auth-1"
    assert start_res.json()["transport"] == "oauth_proxy"

    status_res = await _request("GET", "/ui/engines/auth/sessions/auth-1")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "waiting_user"

    cancel_res = await _request("POST", "/ui/engines/auth/sessions/auth-1/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["canceled"] is True
    assert cancel_res.json()["session"]["status"] == "canceled"

    input_res = await _request(
        "POST",
        "/ui/engines/auth/sessions/auth-1/input",
        json={"kind": "code", "value": "ABCD-EFGH"},
    )
    assert input_res.status_code == 200
    assert input_res.json()["accepted"] is True
    assert input_res.json()["session"]["engine"] == "gemini"


@pytest.mark.asyncio
async def test_ui_engine_auth_grouped_endpoints(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.oauth_proxy_orchestrator.start_session",
        lambda engine, auth_method, provider_id=None, callback_base_url=None: {  # noqa: ARG001
            "session_id": "oauth-ui-1",
            "engine": engine,
            "transport": "oauth_proxy",
            "auth_method": auth_method,
            "provider_id": provider_id,
            "status": "waiting_user",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:01Z",
            "expires_at": "2026-02-27T00:15:00Z",
            "auth_ready": False,
            "terminal": False,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.oauth_proxy_orchestrator.get_session",
        lambda session_id: {
            "session_id": session_id,
            "engine": "codex",
            "transport": "oauth_proxy",
            "auth_method": "callback",
            "status": "waiting_user",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:02Z",
            "expires_at": "2026-02-27T00:15:00Z",
            "auth_ready": False,
            "terminal": False,
        },
    )

    start_res = await _request(
        "POST",
        "/ui/engines/auth/oauth-proxy/sessions",
        json={"engine": "codex", "transport": "oauth_proxy", "auth_method": "callback"},
    )
    assert start_res.status_code == 200
    assert start_res.json()["transport"] == "oauth_proxy"

    status_res = await _request("GET", "/ui/engines/auth/oauth-proxy/sessions/oauth-ui-1")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "waiting_user"


@pytest.mark.asyncio
async def test_ui_engine_auth_start_passes_auth_method(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    captured = {}

    def _start(engine, method, auth_method=None, provider_id=None, transport=None, callback_base_url=None):  # noqa: ANN001
        captured.update(
            {
                "engine": engine,
                "method": method,
                "auth_method": auth_method,
                "provider_id": provider_id,
                "transport": transport,
            }
        )
        return {
            "session_id": "auth-ui-1",
            "engine": engine,
            "method": method,
            "auth_method": auth_method,
            "transport": transport or "oauth_proxy",
            "provider_id": provider_id,
            "status": "waiting_user",
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:01Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        }

    monkeypatch.setattr("server.routers.ui.engine_auth_flow_manager.start_session", _start)
    response = await _request(
        "POST",
        "/ui/engines/auth/sessions",
        json={
            "engine": "opencode",
            "method": "auth",
            "provider_id": "openai",
            "transport": "cli_delegate",
            "auth_method": "auth_code_or_url",
        },
    )
    assert response.status_code == 200
    assert captured["auth_method"] == "auth_code_or_url"
    assert captured["provider_id"] == "openai"


@pytest.mark.asyncio
async def test_ui_engine_auth_session_iflow_start_and_input(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.start_session",
        lambda engine, method, auth_method=None, provider_id=None, transport=None, callback_base_url=None: {
            "session_id": "auth-iflow-1",
            "engine": engine,
            "method": method,
            "provider_id": provider_id,
            "status": "waiting_user",
            "auth_url": "https://iflow.cn/oauth?state=abc",
            "user_code": None,
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:01Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.input_session",
        lambda _session_id, _kind, _value: {
            "session_id": "auth-iflow-1",
            "engine": "iflow",
            "method": "auth",
            "status": "code_submitted_waiting_result",
            "input_kind": "code",
            "auth_url": "https://iflow.cn/oauth?state=abc",
            "user_code": None,
            "created_at": "2026-02-25T00:00:00Z",
            "updated_at": "2026-02-25T00:00:02Z",
            "expires_at": "2026-02-25T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )

    start_res = await _request(
        "POST",
        "/ui/engines/auth/sessions",
        json={"engine": "iflow", "method": "auth"},
    )
    assert start_res.status_code == 200
    assert start_res.json()["engine"] == "iflow"
    assert start_res.json()["method"] == "auth"

    input_res = await _request(
        "POST",
        "/ui/engines/auth/sessions/auth-iflow-1/input",
        json={"kind": "code", "value": "CODE-1234"},
    )
    assert input_res.status_code == 200
    assert input_res.json()["accepted"] is True
    assert input_res.json()["session"]["engine"] == "iflow"


@pytest.mark.asyncio
async def test_ui_engine_auth_submit_removed(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    response = await _request(
        "POST",
        "/ui/engines/auth/sessions/auth-1/submit",
        json={"code": "ABCD"},
    )
    assert response.status_code in {404, 405}


@pytest.mark.asyncio
async def test_ui_engine_auth_session_start_conflict(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)

    def _raise(engine, method, auth_method=None, provider_id=None, transport=None, callback_base_url=None):  # noqa: ARG001
        raise EngineInteractionBusyError("busy")

    monkeypatch.setattr(
        "server.routers.ui.engine_auth_flow_manager.start_session",
        _raise,
    )
    response = await _request(
        "POST",
        "/ui/engines/auth/sessions",
        json={"engine": "codex", "method": "auth"},
    )
    assert response.status_code == 409


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
async def test_ui_engine_models_add_snapshot_rejects_opencode(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)

    response = await _request(
        "POST",
        "/ui/engines/opencode/models/snapshots",
        data={
            "id": ["openai/gpt-5"],
            "display_name": ["OpenAI GPT-5"],
            "deprecated": ["false"],
            "notes": ["runtime_probe_cache"],
            "supported_effort": [""],
        },
    )
    assert response.status_code == 303
    assert "does+not+support+model+snapshots" in response.headers["location"]


@pytest.mark.asyncio
async def test_ui_runs_page_and_table(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_runs",
        lambda limit=200: SimpleNamespace(
            runs=[
                SimpleNamespace(
                    request_id="req-1",
                    run_id="run-1",
                    skill_id="demo-skill",
                    engine="gemini",
                    status="running",
                    pending_interaction_id=None,
                    interaction_count=2,
                    updated_at="2026-01-01T00:00:00",
                )
            ]
        ),
    )

    response = await _request("GET", "/ui/runs")
    assert response.status_code == 200
    assert "Run 观测" in response.text

    table_res = await _request("GET", "/ui/runs/table")
    assert table_res.status_code == 200
    assert table_res.headers.get("Deprecation") == "true"
    assert "req-1" in table_res.text
    assert "/ui/runs/req-1" in table_res.text


@pytest.mark.asyncio
async def test_ui_run_detail_preview_and_logs(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run",
        lambda _request_id: SimpleNamespace(
            request_id="req-1",
            run_id="run-1",
            skill_id="demo-skill",
            engine="gemini",
            status="running",
            updated_at=datetime(2026, 1, 1, 0, 0, 0),
            pending_interaction_id=None,
            interaction_count=1,
            error=None,
        ),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run_files",
        lambda _request_id: SimpleNamespace(
            entries=[{"rel_path": "logs/stdout.txt", "name": "stdout.txt", "is_dir": False, "depth": 1}],
        ),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run_file",
        lambda _request_id, _path: SimpleNamespace(
            path="logs/stdout.txt",
            preview={"mode": "text", "content": "ok", "size": 2, "meta": "2 bytes"},
        ),
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
    assert "对话区（FCMP）" in detail_res.text
    assert "Raw stderr" in detail_res.text
    assert "raw_ref 回跳预览" in detail_res.text
    assert "FCMP Audit Stream" in detail_res.text
    assert "RASP Audit Stream" in detail_res.text
    assert "Orchestrator Audit Stream" in detail_res.text
    assert 'id="run-file-tree-scroll"' in detail_res.text
    assert 'id="run-file-preview-scroll"' in detail_res.text
    assert 'id="fcmp-audit-log"' in detail_res.text
    assert 'id="rasp-audit-log"' in detail_res.text
    assert 'id="orchestrator-audit-log"' in detail_res.text
    assert 'id="raw-ref-preview"' in detail_res.text
    assert "/v1/management/runs/${requestId}/events" in detail_res.text
    assert "/v1/management/runs/${requestId}/protocol/history?" in detail_res.text
    assert "/v1/management/runs/${requestId}/logs/range" in detail_res.text
    assert "connectEvents()" in detail_res.text
    assert detail_res.text.index("raw_ref 回跳预览") < detail_res.text.index("Attempt:")
    assert detail_res.text.index("对话区（FCMP）") < detail_res.text.index("Attempt:")
    assert detail_res.text.index("Attempt:") < detail_res.text.index("FCMP Audit Stream")
    assert detail_res.text.rindex("Raw stderr") > detail_res.text.index("FCMP Audit Stream")

    preview_res = await _request("GET", "/ui/runs/req-1/view?path=logs/stdout.txt")
    assert preview_res.status_code == 200
    assert preview_res.headers.get("Deprecation") == "true"
    assert "ok" in preview_res.text

    logs_res = await _request("GET", "/ui/runs/req-1/logs/tail")
    assert logs_res.status_code == 200
    assert logs_res.headers.get("Deprecation") == "true"
    assert "stream-out" in logs_res.text
    assert "every 2s" in logs_res.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["running", "waiting_user", "canceled"])
async def test_ui_run_detail_conversation_states(monkeypatch, status: str):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run",
        lambda _request_id: SimpleNamespace(
            request_id="req-x",
            run_id="run-x",
            skill_id="demo",
            engine="gemini",
            status=status,
            updated_at=datetime(2026, 1, 1, 0, 0, 0),
            pending_interaction_id=7 if status == "waiting_user" else None,
            interaction_count=4,
            error=None,
        ),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run_files",
        lambda _request_id: SimpleNamespace(entries=[]),
    )

    response = await _request("GET", "/ui/runs/req-x")
    assert response.status_code == 200
    assert f">{status}<" in response.text
    assert "/v1/management/runs/${requestId}/events" in response.text
    assert "/v1/management/runs/${requestId}/protocol/history?" in response.text
    assert "/v1/management/runs/${requestId}/cancel" in response.text
    assert "/v1/management/runs/${requestId}/logs/range" in response.text
    assert "cursor=${cursor}" in response.text
    assert 'id="stdout-log"' in response.text
    assert 'id="stderr-log"' in response.text
    assert 'id="fcmp-audit-log"' in response.text
    assert 'id="rasp-audit-log"' in response.text
    assert 'id="orchestrator-audit-log"' in response.text
    assert 'id="cancel-run-btn"' in response.text


@pytest.mark.asyncio
async def test_ui_pages_use_management_data_endpoints(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_skills",
        lambda: SimpleNamespace(skills=[]),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_engines",
        lambda: SimpleNamespace(engines=[]),
    )

    index_res = await _request("GET", "/ui")
    assert index_res.status_code == 200
    assert '/ui/management/skills/table' in index_res.text

    engines_res = await _request("GET", "/ui/engines")
    assert engines_res.status_code == 200
    assert '/ui/management/engines/table' in engines_res.text

    runs_res = await _request("GET", "/ui/runs")
    assert runs_res.status_code == 200
    assert '/ui/management/runs/table' in runs_res.text


@pytest.mark.asyncio
async def test_ui_legacy_data_endpoint_can_switch_to_410(monkeypatch):
    monkeypatch.setattr("server.services.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.ui_auth.is_ui_basic_auth_enabled", lambda: False)
    monkeypatch.setattr("server.routers.ui.LEGACY_UI_DATA_API_MODE", "gone")

    response = await _request("GET", "/ui/skills/table")
    assert response.status_code == 410
