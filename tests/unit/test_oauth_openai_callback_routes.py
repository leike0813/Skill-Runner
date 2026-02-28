from contextlib import asynccontextmanager

import pytest

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
async def test_openai_callback_route_success(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.complete_callback",
        lambda channel, state, code=None, error=None: {  # noqa: ARG005
            "status": "succeeded",
            "error": None,
        },
    )
    response = await _request(
        "GET",
        "/v1/engines/auth/callback/openai?state=session-state&code=auth-code",
    )
    assert response.status_code == 200
    assert "OAuth authorization successful" in response.text

    alias_response = await _request(
        "GET",
        "/auth/callback?state=session-state&code=auth-code",
    )
    assert alias_response.status_code == 200
    assert "OAuth authorization successful" in alias_response.text


@pytest.mark.asyncio
async def test_openai_callback_route_replay(monkeypatch):
    def _raise(channel, state, code=None, error=None):  # noqa: ARG001
        raise ValueError("OAuth callback state has already been consumed")

    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.complete_callback",
        _raise,
    )
    response = await _request(
        "GET",
        "/v1/engines/auth/callback/openai?state=replayed-state&code=auth-code",
    )
    assert response.status_code == 400
    assert "already been consumed" in response.text
