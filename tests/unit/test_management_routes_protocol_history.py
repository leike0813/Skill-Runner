from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_name", ["fcmp", "rasp", "orchestrator"])
async def test_management_protocol_history_streams(monkeypatch, tmp_path: Path, stream_name: str):
    run_dir = tmp_path / "run-protocol"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        lambda _request_id: {"request_id": "req-1", "run_id": "run-protocol"},
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    def _list_protocol_history(**kwargs):
        assert kwargs["stream"] == stream_name
        return {
            "attempt": 2,
            "available_attempts": [1, 2],
            "events": [{"seq": 1, "type": f"{stream_name}.event"}],
        }

    monkeypatch.setattr(
        "server.routers.management.run_observability_service.list_protocol_history",
        _list_protocol_history,
    )

    response = await _request(
        "GET",
        f"/v1/management/runs/req-1/protocol/history?stream={stream_name}",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-1"
    assert payload["stream"] == stream_name
    assert payload["attempt"] == 2
    assert payload["available_attempts"] == [1, 2]
    assert payload["count"] == 1
    assert payload["events"][0]["seq"] == 1


@pytest.mark.asyncio
async def test_management_protocol_history_filters(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-protocol"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        lambda _request_id: {"request_id": "req-1", "run_id": "run-protocol"},
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    def _list_protocol_history(**kwargs):
        assert kwargs["stream"] == "fcmp"
        assert kwargs["from_seq"] == 10
        assert kwargs["to_seq"] == 20
        assert kwargs["from_ts"] == "2026-02-24T00:00:00"
        assert kwargs["to_ts"] == "2026-02-24T00:10:00"
        assert kwargs["attempt"] == 3
        return {
            "attempt": 3,
            "available_attempts": [1, 2, 3],
            "events": [{"seq": 15, "type": "conversation.state.changed"}],
        }

    monkeypatch.setattr(
        "server.routers.management.run_observability_service.list_protocol_history",
        _list_protocol_history,
    )

    response = await _request(
        "GET",
        "/v1/management/runs/req-1/protocol/history"
        "?stream=fcmp&from_seq=10&to_seq=20"
        "&from_ts=2026-02-24T00:00:00&to_ts=2026-02-24T00:10:00"
        "&attempt=3",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["attempt"] == 3
    assert payload["available_attempts"] == [1, 2, 3]
    assert payload["count"] == 1
    assert payload["events"][0]["seq"] == 15


@pytest.mark.asyncio
async def test_management_protocol_history_rejects_invalid_stream(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-protocol"
    run_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "server.routers.management.run_store.get_request",
        lambda _request_id: {"request_id": "req-1", "run_id": "run-protocol"},
    )
    monkeypatch.setattr(
        "server.routers.management.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    response = await _request(
        "GET",
        "/v1/management/runs/req-1/protocol/history?stream=unknown",
    )
    assert response.status_code == 400
    assert "stream must be one of" in response.text
