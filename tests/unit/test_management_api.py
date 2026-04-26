from contextlib import asynccontextmanager
import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.config import config  # noqa: E402
from server.engines.claude.adapter.state_paths import active_claude_state_path  # noqa: E402
from server.main import app  # noqa: E402
from server.services.mcp import clear_mcp_registry_cache  # noqa: E402


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
async def test_management_mcp_crud_never_echoes_raw_keys() -> None:
    clear_mcp_registry_cache()
    request_payload = {
        "activation": "default",
        "engines": ["codex"],
        "unsupported_engines": [],
        "scope": "run-local",
        "transport": "http",
        "url": "https://mcp.example/sse",
        "auth": {
            "env": [],
            "headers": [
                {
                    "name": "Authorization",
                    "prefix": "Bearer ",
                    "value": "raw-token",
                }
            ],
        },
    }

    upsert_res = await _request("PUT", "/v1/management/mcp/servers/demo", json=request_payload)
    assert upsert_res.status_code == 200
    upsert_payload = upsert_res.json()
    assert "raw-token" not in json.dumps(upsert_payload)
    assert upsert_payload["auth"]["headers"][0]["configured"] is True
    assert upsert_payload["auth"]["headers"][0]["masked_value"] == "********"

    registry_payload = json.loads(Path(config.SYSTEM.MCP_REGISTRY_FILE).read_text(encoding="utf-8"))
    assert "raw-token" not in json.dumps(registry_payload)
    assert registry_payload["servers"]["demo"]["auth"]["headers"][0]["secret_id"]
    secrets_payload = json.loads(Path(config.SYSTEM.MCP_SECRETS_FILE).read_text(encoding="utf-8"))
    assert "raw-token" in secrets_payload["secrets"].values()

    list_res = await _request("GET", "/v1/management/mcp/servers")
    assert list_res.status_code == 200
    assert "raw-token" not in list_res.text
    assert list_res.json()["servers"][0]["id"] == "demo"

    preserve_payload = dict(request_payload)
    preserve_payload["auth"] = {
        "env": [],
        "headers": [{"name": "Authorization", "prefix": "Bearer ", "value": ""}],
    }
    preserve_res = await _request("PUT", "/v1/management/mcp/servers/demo", json=preserve_payload)
    assert preserve_res.status_code == 200
    secrets_payload = json.loads(Path(config.SYSTEM.MCP_SECRETS_FILE).read_text(encoding="utf-8"))
    assert "raw-token" in secrets_payload["secrets"].values()

    delete_res = await _request("DELETE", "/v1/management/mcp/servers/demo")
    assert delete_res.status_code == 200
    assert delete_res.json()["deleted"] is True
    secrets_payload = json.loads(Path(config.SYSTEM.MCP_SECRETS_FILE).read_text(encoding="utf-8"))
    assert "raw-token" not in secrets_payload["secrets"].values()


@pytest.mark.asyncio
async def test_management_mcp_rejects_new_auth_without_value() -> None:
    clear_mcp_registry_cache()
    response = await _request(
        "PUT",
        "/v1/management/mcp/servers/demo",
        json={
            "activation": "declared",
            "scope": "run-local",
            "transport": "stdio",
            "command": "python",
            "auth": {
                "env": [{"name": "API_KEY", "value": ""}],
                "headers": [],
            },
        },
    )

    assert response.status_code == 422
    assert "requires a value" in response.text


@pytest.mark.asyncio
async def test_management_mcp_syncs_claude_agent_home_state() -> None:
    clear_mcp_registry_cache()
    agent_home = Path(config.SYSTEM.AGENT_HOME)
    active_path = active_claude_state_path(agent_home)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(
        json.dumps({"mcpServers": {"user-server": {"type": "http", "url": "https://user.example/mcp"}}}),
        encoding="utf-8",
    )
    request_payload = {
        "activation": "default",
        "engines": ["claude"],
        "unsupported_engines": [],
        "scope": "agent-home",
        "transport": "http",
        "url": "https://mcp.example/http",
        "auth": {
            "env": [],
            "headers": [
                {
                    "name": "Authorization",
                    "prefix": "Bearer ",
                    "value": "raw-token",
                }
            ],
        },
    }

    upsert_res = await _request("PUT", "/v1/management/mcp/servers/demo", json=request_payload)

    assert upsert_res.status_code == 200
    active_payload = json.loads(active_path.read_text(encoding="utf-8"))
    assert active_payload["mcpServers"]["user-server"]["url"] == "https://user.example/mcp"
    assert active_payload["mcpServers"]["demo"] == {
        "type": "http",
        "url": "https://mcp.example/http",
        "headers": {"Authorization": "Bearer raw-token"},
    }

    delete_res = await _request("DELETE", "/v1/management/mcp/servers/demo")

    assert delete_res.status_code == 200
    active_payload = json.loads(active_path.read_text(encoding="utf-8"))
    assert "demo" not in active_payload["mcpServers"]
    assert "user-server" in active_payload["mcpServers"]
