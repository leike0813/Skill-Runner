import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_temp_skill_runs_create_route_removed():
    response = await _request(
        "POST",
        "/v1/temp-skill-runs",
        json={"engine": "gemini", "parameter": {}, "runtime_options": {}},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_temp_skill_runs_upload_route_removed():
    response = await _request(
        "POST",
        "/v1/temp-skill-runs/does-not-exist/upload",
        files={"skill_package": ("skill.zip", b"dummy", "application/zip")},
    )
    assert response.status_code == 404
