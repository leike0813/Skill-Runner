from contextlib import asynccontextmanager

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
async def test_management_logs_range_forwards_attempt(monkeypatch):
    captured: dict[str, object] = {}

    async def _logs_range(**kwargs):
        captured.update(kwargs)
        return {"stream": "stdout", "byte_from": 0, "byte_to": 4, "chunk": "demo"}

    monkeypatch.setattr("server.routers.management.jobs_router.get_run_log_range", _logs_range)

    response = await _request(
        "GET",
        "/v1/management/runs/req-1/logs/range?stream=stdout&byte_from=0&byte_to=4&attempt=2",
    )
    assert response.status_code == 200
    assert captured["request_id"] == "req-1"
    assert captured["attempt"] == 2
