from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_management_timeline_history_success(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-timeline"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        AsyncMock(return_value={"request_id": "req-1", "run_id": "run-timeline"}),
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    async def _list_timeline_history(**kwargs):
        assert kwargs["cursor"] == 12
        assert kwargs["limit"] == 50
        return {
            "events": [
                {
                    "timeline_seq": 13,
                    "ts": "2026-03-06T10:00:00Z",
                    "lane": "protocol_fcmp",
                    "kind": "conversation.state.changed",
                    "summary": "state: queued -> running",
                    "attempt": 2,
                    "source_stream": "fcmp",
                    "details": {"stream": "fcmp"},
                }
            ],
            "cursor_floor": 13,
            "cursor_ceiling": 42,
            "source": "mixed",
        }

    monkeypatch.setattr(
        "server.routers.management.run_observability_service.list_timeline_history",
        _list_timeline_history,
    )

    response = await _request(
        "GET",
        "/v1/management/runs/req-1/timeline/history?cursor=12&limit=50",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-1"
    assert payload["count"] == 1
    assert payload["cursor_floor"] == 13
    assert payload["cursor_ceiling"] == 42
    assert payload["source"] == "mixed"
    assert payload["events"][0]["timeline_seq"] == 13
    assert payload["events"][0]["lane"] == "protocol_fcmp"


@pytest.mark.asyncio
async def test_management_timeline_history_request_or_run_not_found(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        AsyncMock(return_value=None),
    )
    missing_request = await _request("GET", "/v1/management/runs/req-missing/timeline/history")
    assert missing_request.status_code == 404
    assert "Request not found" in missing_request.text

    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        AsyncMock(return_value={"request_id": "req-2", "run_id": "run-2"}),
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: tmp_path / "does-not-exist",
    )
    missing_run = await _request("GET", "/v1/management/runs/req-2/timeline/history")
    assert missing_run.status_code == 404
    assert "Run directory not found" in missing_run.text
