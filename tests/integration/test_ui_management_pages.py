from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


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


@pytest.mark.asyncio
async def test_ui_pages_render_with_management_api_sources(monkeypatch):
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
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_runs",
        lambda limit=200: SimpleNamespace(runs=[]),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run",
        lambda _request_id: SimpleNamespace(
            request_id="req-ui",
            run_id="run-ui",
            skill_id="demo",
            engine="gemini",
            status="running",
            updated_at=datetime(2026, 1, 1, 0, 0, 0),
            pending_interaction_id=None,
            interaction_count=0,
            error=None,
        ),
    )
    monkeypatch.setattr(
        "server.routers.ui.management_router.get_management_run_files",
        lambda _request_id: SimpleNamespace(entries=[]),
    )

    index = await _request("GET", "/ui")
    assert index.status_code == 200
    assert "/ui/management/skills/table" in index.text

    engines = await _request("GET", "/ui/engines")
    assert engines.status_code == 200
    assert "/ui/management/engines/table" in engines.text

    runs = await _request("GET", "/ui/runs")
    assert runs.status_code == 200
    assert "/ui/management/runs/table" in runs.text

    run_detail = await _request("GET", "/ui/runs/req-ui")
    assert run_detail.status_code == 200
    assert "/v1/management/runs/${requestId}/events" in run_detail.text


@pytest.mark.asyncio
async def test_ui_legacy_data_routes_emit_deprecation_headers(monkeypatch):
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
    monkeypatch.setattr(
        "server.routers.ui.management_router.list_management_runs",
        lambda limit=200: SimpleNamespace(runs=[]),
    )

    skills = await _request("GET", "/ui/skills/table")
    assert skills.status_code == 200
    assert skills.headers.get("Deprecation") == "true"

    engines = await _request("GET", "/ui/engines/table")
    assert engines.status_code == 200
    assert engines.headers.get("Deprecation") == "true"

    runs = await _request("GET", "/ui/runs/table")
    assert runs.status_code == 200
    assert runs.headers.get("Deprecation") == "true"
