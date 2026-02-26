import pytest
import json

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.services.engine_interaction_gate import EngineInteractionBusyError
from server.services.engine_upgrade_manager import EngineUpgradeBusyError, EngineUpgradeValidationError


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/skills",
        "/runs",
        "/engines",
        "/management/runs/does-not-exist",
        "/runs/does-not-exist",
        "/engines/codex/models",
        "/jobs/does-not-exist/interaction/pending",
    ],
)
async def test_legacy_routes_return_404(path):
    response = await _request("GET", path)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_skills_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.skills.skill_registry.list_skills",
        lambda: [],
    )
    response = await _request("GET", "/v1/skills")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_v1_engines_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.list_engines",
        lambda: [{"engine": "codex", "cli_version_detected": "0.89.0"}],
    )
    response = await _request("GET", "/v1/engines")
    assert response.status_code == 200
    body = response.json()
    assert body["engines"][0]["engine"] == "codex"


@pytest.mark.asyncio
async def test_v1_engine_auth_status_route(monkeypatch):
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
    response = await _request("GET", "/v1/engines/auth-status")
    assert response.status_code == 200
    body = response.json()
    assert body["engines"]["codex"]["effective_path_source"] == "managed"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_start_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        lambda engine, method, provider_id=None: {
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
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "codex", "method": "device-auth"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "auth-1"
    assert body["status"] == "waiting_user"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_start_route_iflow(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        lambda engine, method, provider_id=None: {
            "session_id": "auth-iflow-1",
            "engine": engine,
            "method": method,
            "provider_id": provider_id,
            "status": "waiting_user",
            "auth_url": "https://iflow.cn/oauth?state=abc",
            "user_code": None,
            "created_at": "2026-02-26T00:00:00Z",
            "updated_at": "2026-02-26T00:00:01Z",
            "expires_at": "2026-02-26T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "iflow", "method": "iflow-cli-oauth"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "auth-iflow-1"
    assert body["engine"] == "iflow"
    assert body["method"] == "iflow-cli-oauth"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_start_route_opencode(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        lambda engine, method, provider_id=None: {
            "session_id": "auth-opencode-1",
            "engine": engine,
            "method": method,
            "provider_id": provider_id,
            "provider_name": "DeepSeek",
            "status": "waiting_user",
            "input_kind": "api_key",
            "auth_url": None,
            "user_code": None,
            "created_at": "2026-02-26T00:00:00Z",
            "updated_at": "2026-02-26T00:00:01Z",
            "expires_at": "2026-02-26T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "opencode", "method": "opencode-provider-auth", "provider_id": "deepseek"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "auth-opencode-1"
    assert body["provider_id"] == "deepseek"
    assert body["input_kind"] == "api_key"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_start_conflict(monkeypatch):
    def _raise(engine, method, provider_id=None):  # noqa: ARG001
        raise EngineInteractionBusyError("busy")

    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        _raise,
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "codex", "method": "device-auth"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_v1_engine_auth_session_start_unprocessable(monkeypatch):
    def _raise(engine, method, provider_id=None):  # noqa: ARG001
        raise ValueError("unsupported")

    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.start_session",
        _raise,
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions",
        json={"engine": "gemini", "method": "device-auth"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_v1_engine_auth_session_status_and_cancel(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.get_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "method": "device-auth",
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
        "server.routers.engines.engine_auth_flow_manager.cancel_session",
        lambda _session_id: {
            "session_id": "auth-1",
            "engine": "codex",
            "method": "device-auth",
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

    status_res = await _request("GET", "/v1/engines/auth/sessions/auth-1")
    assert status_res.status_code == 200
    assert status_res.json()["session_id"] == "auth-1"

    cancel_res = await _request("POST", "/v1/engines/auth/sessions/auth-1/cancel")
    assert cancel_res.status_code == 200
    payload = cancel_res.json()
    assert payload["canceled"] is True
    assert payload["session"]["status"] == "canceled"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_input(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.input_session",
        lambda _session_id, _kind, _value: {
            "session_id": "auth-g-1",
            "engine": "gemini",
            "method": "screen-reader-google-oauth",
            "status": "code_submitted_waiting_result",
            "input_kind": "code",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?foo=bar",
            "user_code": None,
            "created_at": "2026-02-26T00:00:00Z",
            "updated_at": "2026-02-26T00:00:02Z",
            "expires_at": "2026-02-26T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions/auth-g-1/input",
        json={"kind": "code", "value": "ABCD-EFGH"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["session"]["engine"] == "gemini"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_input_iflow(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.input_session",
        lambda _session_id, _kind, _value: {
            "session_id": "auth-iflow-1",
            "engine": "iflow",
            "method": "iflow-cli-oauth",
            "status": "code_submitted_waiting_result",
            "input_kind": "code",
            "auth_url": "https://iflow.cn/oauth?state=abc",
            "user_code": None,
            "created_at": "2026-02-26T00:00:00Z",
            "updated_at": "2026-02-26T00:00:02Z",
            "expires_at": "2026-02-26T00:15:00Z",
            "auth_ready": False,
            "error": None,
            "exit_code": None,
            "terminal": False,
        },
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions/auth-iflow-1/input",
        json={"kind": "code", "value": "CODE-1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["session"]["engine"] == "iflow"


@pytest.mark.asyncio
async def test_v1_engine_auth_session_input_unprocessable(monkeypatch):
    def _raise(_session_id, _kind, _value):
        raise ValueError("unsupported")

    monkeypatch.setattr(
        "server.routers.engines.engine_auth_flow_manager.input_session",
        _raise,
    )
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions/auth-1/input",
        json={"kind": "code", "value": "ABCD"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_v1_engine_auth_session_submit_removed():
    response = await _request(
        "POST",
        "/v1/engines/auth/sessions/auth-1/submit",
        json={"code": "ABCD"},
    )
    assert response.status_code in {404, 405}


@pytest.mark.asyncio
async def test_v1_engine_auth_session_status_not_found(monkeypatch):
    def _raise(_session_id):
        raise KeyError("missing")

    monkeypatch.setattr("server.routers.engines.engine_auth_flow_manager.get_session", _raise)
    response = await _request("GET", "/v1/engines/auth/sessions/missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_engine_models_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_models",
        lambda engine: type(
            "Catalog",
            (),
            {
                "engine": engine,
                "cli_version_detected": "0.89.0",
                "snapshot_version_used": "0.89.0",
                "source": "pinned_snapshot",
                "fallback_reason": None,
                "models": [
                    type(
                        "Entry",
                        (),
                        {
                            "id": "gpt-5.2-codex",
                            "display_name": "GPT-5.2 Codex",
                            "deprecated": False,
                            "notes": "snapshot",
                            "supported_effort": ["low", "high"],
                            "provider": None,
                            "model": None,
                        },
                    )()
                ],
            },
        )(),
    )
    response = await _request("GET", "/v1/engines/codex/models")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "codex"
    assert body["models"][0]["id"] == "gpt-5.2-codex"
    assert body["source"] == "pinned_snapshot"


@pytest.mark.asyncio
async def test_v1_engine_models_route_opencode_runtime_probe_cache(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_models",
        lambda engine: type(
            "Catalog",
            (),
            {
                "engine": engine,
                "cli_version_detected": "0.1.0",
                "snapshot_version_used": "2026-02-25T00:00:00Z",
                "source": "runtime_probe_cache",
                "fallback_reason": None,
                "models": [
                    type(
                        "Entry",
                        (),
                        {
                            "id": "openai/gpt-5",
                            "display_name": "OpenAI GPT-5",
                            "deprecated": False,
                            "notes": "runtime_probe_cache",
                            "supported_effort": None,
                            "provider": "openai",
                            "model": "gpt-5",
                        },
                    )()
                ],
            },
        )(),
    )
    response = await _request("GET", "/v1/engines/opencode/models")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "runtime_probe_cache"
    assert body["models"][0]["provider"] == "openai"
    assert body["models"][0]["model"] == "gpt-5"


@pytest.mark.asyncio
async def test_v1_engine_models_not_found(monkeypatch):
    def _raise(_engine: str):
        raise ValueError("Unknown engine")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = await _request("GET", "/v1/engines/unknown/models")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_engine_models_error(monkeypatch):
    def _raise(_engine: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = await _request("GET", "/v1/engines/codex/models")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_v1_runs_route_available():
    response = await _request("GET", "/v1/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_jobs_interaction_routes_available():
    pending = await _request("GET", "/v1/jobs/does-not-exist/interaction/pending")
    assert pending.status_code == 404
    reply = await _request(
        "POST",
        "/v1/jobs/does-not-exist/interaction/reply",
        json={"interaction_id": 1, "response": {"answer": "x"}},
    )
    assert reply.status_code == 404


@pytest.mark.asyncio
async def test_v1_jobs_cancel_route_available():
    response = await _request("POST", "/v1/jobs/does-not-exist/cancel")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_temp_skill_runs_cancel_route_available():
    response = await _request("POST", "/v1/temp-skill-runs/does-not-exist/cancel")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_temp_skill_runs_interaction_and_history_routes_available():
    pending = await _request("GET", "/v1/temp-skill-runs/does-not-exist/interaction/pending")
    assert pending.status_code == 404

    reply = await _request(
        "POST",
        "/v1/temp-skill-runs/does-not-exist/interaction/reply",
        json={"interaction_id": 1, "response": {"answer": "x"}},
    )
    assert reply.status_code == 404

    history = await _request("GET", "/v1/temp-skill-runs/does-not-exist/events/history")
    assert history.status_code == 404

    logs_range = await _request(
        "GET",
        "/v1/temp-skill-runs/does-not-exist/logs/range?stream=stdout&byte_from=0&byte_to=10",
    )
    assert logs_range.status_code == 404


@pytest.mark.asyncio
async def test_v1_management_routes_available():
    run_res = await _request("GET", "/v1/management/runs/does-not-exist")
    assert run_res.status_code == 404
    skill_res = await _request("GET", "/v1/management/skills/does-not-exist")
    assert skill_res.status_code == 404
    pending_res = await _request("GET", "/v1/management/runs/does-not-exist/pending")
    assert pending_res.status_code == 404
    cancel_res = await _request("POST", "/v1/management/runs/does-not-exist/cancel")
    assert cancel_res.status_code == 404


@pytest.mark.asyncio
async def test_v1_jobs_events_stream_snapshot_and_terminal(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-1"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("hello", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("err", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-1"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )

    response = await _request("GET", "/v1/jobs/req-1/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: snapshot" in response.text
    assert "event: chat_event" in response.text
    assert "event: stdout" not in response.text
    assert "event: stderr" not in response.text
    assert "event: end" not in response.text


@pytest.mark.asyncio
async def test_v1_temp_skill_run_events_stream_available(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-temp"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.routers.temp_skill_runs.temp_skill_run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-temp"},
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: {"interaction_id": 1, "kind": "open_text", "prompt": "continue"},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )

    response = await _request("GET", "/v1/temp-skill-runs/temp-1/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: snapshot" in response.text
    assert "event: chat_event" in response.text
    assert "event: status" not in response.text
    assert "event: end" not in response.text


@pytest.mark.asyncio
async def test_v1_jobs_events_cursor_skips_old_chat_events(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-2"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "stdout.txt"
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    stdout_path.write_text("part-1\n", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-2",
            "runtime_options": {"execution_mode": "interactive"},
        },
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: {"interaction_id": 1},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )

    first = await _request("GET", "/v1/jobs/req-2/events")
    assert first.status_code == 200
    assert "event: chat_event" in first.text
    assert "\"user.input.required\"" in first.text

    stdout_path.write_text("part-1\npart-2\n", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:01"}),
        encoding="utf-8",
    )

    second = await _request(
        "GET",
        "/v1/jobs/req-2/events?cursor=999",
    )
    assert second.status_code == 200
    assert "event: chat_event" not in second.text


@pytest.mark.asyncio
async def test_v1_jobs_events_canceled_includes_error_code(tmp_path, monkeypatch):
    run_dir = tmp_path / "run-canceled"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("before-cancel\n", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "canceled",
                "updated_at": "2026-01-01T00:00:00",
                "error": {"code": "CANCELED_BY_USER", "message": "Canceled by user request"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-canceled"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: None,
    )

    response = await _request("GET", "/v1/jobs/req-canceled/events")
    assert response.status_code == 200
    assert "\"conversation.failed\"" in response.text
    assert "\"CANCELED\"" in response.text


@pytest.mark.asyncio
async def test_v1_jobs_events_history_route(monkeypatch, tmp_path):
    run_dir = tmp_path / "run-history"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-history"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_observability_service.list_event_history",
        lambda **_kwargs: [
            {"seq": 2, "event": {"type": "agent.message.final"}},
            {"seq": 3, "event": {"type": "lifecycle.run.terminal"}},
        ],
    )

    response = await _request(
        "GET",
        "/v1/jobs/req-history/events/history?from_seq=2&to_seq=3",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-history"
    assert payload["count"] == 2
    assert payload["events"][0]["seq"] == 2


@pytest.mark.asyncio
async def test_v1_jobs_log_range_route(monkeypatch, tmp_path):
    run_dir = tmp_path / "run-log-range"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.routers.jobs.run_store.get_request",
        lambda request_id: {"request_id": request_id, "run_id": "run-log-range"},
    )
    monkeypatch.setattr(
        "server.routers.jobs.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )
    monkeypatch.setattr(
        "server.routers.jobs.run_observability_service.read_log_range",
        lambda **_kwargs: {
            "stream": "stdout",
            "byte_from": 1,
            "byte_to": 4,
            "chunk": "abc",
        },
    )

    response = await _request(
        "GET",
        "/v1/jobs/req-log-range/logs/range?stream=stdout&byte_from=1&byte_to=4",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["stream"] == "stdout"
    assert payload["chunk"] == "abc"


@pytest.mark.asyncio
async def test_v1_jobs_cleanup_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.jobs.run_cleanup_manager.clear_all",
        lambda: {"runs": 1, "requests": 2, "cache_entries": 3},
    )
    response = await _request("POST", "/v1/jobs/cleanup")
    assert response.status_code == 200
    body = response.json()
    assert body["runs_deleted"] == 1
    assert body["requests_deleted"] == 2
    assert body["cache_entries_deleted"] == 3


@pytest.mark.asyncio
async def test_v1_temp_skill_runs_route_available():
    response = await _request("GET", "/v1/temp-skill-runs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_upgrade_manager.create_task",
        lambda mode, engine: "upgrade-1",
    )
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "all"})
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "upgrade-1"
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_conflict(monkeypatch):
    def _raise(_mode, _engine):
        raise EngineUpgradeBusyError("busy")

    monkeypatch.setattr("server.routers.engines.engine_upgrade_manager.create_task", _raise)
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "all"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_validation_error(monkeypatch):
    def _raise(_mode, _engine):
        raise EngineUpgradeValidationError("bad payload")

    monkeypatch.setattr("server.routers.engines.engine_upgrade_manager.create_task", _raise)
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "bad"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_v1_engine_upgrade_status_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_upgrade_manager.get_task",
        lambda _request_id: {
            "request_id": "upgrade-1",
            "mode": "all",
            "requested_engine": None,
            "status": "running",
            "results": {
                "codex": {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}
            },
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:01",
        },
    )
    response = await _request("GET", "/v1/engines/upgrades/upgrade-1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["results"]["codex"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_v1_engine_manifest_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_manifest_view",
        lambda _engine: {
            "engine": "codex",
            "cli_version_detected": "0.89.0",
            "manifest": {"engine": "codex", "snapshots": []},
            "resolved_snapshot_version": "0.89.0",
            "resolved_snapshot_file": "models_0.89.0.json",
            "fallback_reason": None,
            "models": [{"id": "gpt-5.2-codex", "deprecated": False}],
        },
    )
    response = await _request("GET", "/v1/engines/codex/models/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "codex"
    assert body["resolved_snapshot_file"] == "models_0.89.0.json"


@pytest.mark.asyncio
async def test_v1_engine_snapshot_route_conflict(monkeypatch):
    def _raise(_engine, _models):
        raise ValueError("Snapshot already exists for version 0.89.0")

    monkeypatch.setattr("server.routers.engines.model_registry.add_snapshot_for_detected_version", _raise)
    response = await _request(
        "POST",
        "/v1/engines/codex/models/snapshots",
        json={"models": [{"id": "gpt-5.2-codex"}]},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_v1_engine_snapshot_route_opencode_not_supported(monkeypatch):
    def _raise(_engine, _models):
        raise ValueError("Engine 'opencode' does not support model snapshots")

    monkeypatch.setattr("server.routers.engines.model_registry.add_snapshot_for_detected_version", _raise)
    response = await _request(
        "POST",
        "/v1/engines/opencode/models/snapshots",
        json={"models": [{"id": "openai/gpt-5"}]},
    )
    assert response.status_code == 409
