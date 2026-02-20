from contextlib import asynccontextmanager
import io
from pathlib import Path
from typing import Any
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from e2e_client.app import create_app
from e2e_client.recording import RecordingStore
from e2e_client.routes import get_backend_client


class FakeBackend:
    def __init__(self):
        self.reply_payloads: list[dict[str, Any]] = []
        self.create_payloads: list[dict[str, Any]] = []

    async def list_skills(self) -> dict[str, Any]:
        return {
            "skills": [
                {
                    "id": "demo-skill",
                    "name": "Demo Skill",
                    "version": "1.0.0",
                    "engines": ["gemini"],
                    "health": "healthy",
                }
            ]
        }

    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "id": "demo-skill",
            "name": "Demo Skill",
            "version": "1.0.0",
            "engines": ["gemini"],
            "execution_modes": ["auto", "interactive"],
        }

    async def get_skill_schemas(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "skill_id": skill_id,
            "input": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "x-input-source": "inline"},
                    "input_file": {"type": "string"},
                },
                "required": ["prompt", "input_file"],
            },
            "parameter": {
                "type": "object",
                "properties": {"top_k": {"type": "integer"}},
                "required": ["top_k"],
            },
            "output": {"type": "object"},
        }

    async def get_engine_detail(self, engine: str) -> dict[str, Any]:
        assert engine == "gemini"
        return {
            "engine": "gemini",
            "models": [
                {"id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro"},
                {"id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash"},
            ],
        }

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["skill_id"] == "demo-skill"
        self.create_payloads.append(payload)
        return {"request_id": "req-e2e-1", "status": "queued", "cache_hit": False}

    async def upload_run_file(self, request_id: str, zip_bytes: bytes) -> dict[str, Any]:
        assert request_id == "req-e2e-1"
        assert zip_bytes
        return {"request_id": request_id, "cache_hit": False, "extracted_files": ["input_file"]}

    async def get_run_state(self, request_id: str) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "run_id": "run-e2e-1",
            "status": "waiting_user",
            "pending_interaction_id": 7,
        }

    async def get_run_pending(self, request_id: str) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "status": "waiting_user",
            "pending": {
                "interaction_id": 7,
                "kind": "open_text",
                "prompt": "Please confirm",
            },
        }

    async def post_run_reply(self, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.reply_payloads.append(payload)
        return {"request_id": request_id, "status": "queued", "accepted": True}

    async def get_run_result(self, request_id: str) -> dict[str, Any]:
        return {"request_id": request_id, "result": {"answer": "ok"}}

    async def get_run_artifacts(self, request_id: str) -> dict[str, Any]:
        return {"request_id": request_id, "artifacts": ["artifacts/out.txt"]}

    async def get_run_bundle(self, request_id: str) -> bytes:
        del request_id
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("result/result.json", '{"answer":"ok"}')
            archive.writestr("artifacts/out.txt", "artifact text")
        return buffer.getvalue()

    async def stream_run_events(
        self,
        request_id: str,
        *,
        stdout_from: int = 0,
        stderr_from: int = 0,
    ):
        del request_id, stdout_from, stderr_from
        yield b'event: snapshot\ndata: {"status":"running"}\n\n'
        yield b'event: stdout\ndata: {"chunk":"hello"}\n\n'
        yield b'event: end\ndata: {"reason":"waiting_user"}\n\n'


class FakeBackendEffectiveEnginesOnly(FakeBackend):
    async def list_skills(self) -> dict[str, Any]:
        return {
            "skills": [
                {
                    "id": "demo-skill",
                    "name": "Demo Skill",
                    "version": "1.0.0",
                    "engines": [],
                    "effective_engines": ["gemini"],
                    "health": "healthy",
                }
            ]
        }

    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "id": "demo-skill",
            "name": "Demo Skill",
            "version": "1.0.0",
            "engines": [],
            "effective_engines": ["gemini"],
            "execution_modes": ["auto", "interactive"],
        }


async def _request(app, method: str, path: str, **kwargs):
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
async def test_e2e_example_client_full_flow(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    app.dependency_overrides[get_backend_client] = lambda: fake_backend
    try:
        home = await _request(app, "GET", "/")
        assert home.status_code == 200
        assert "Demo Skill" in home.text

        run_form = await _request(app, "GET", "/skills/demo-skill/run")
        assert run_form.status_code == 200
        assert "Inline Input" in run_form.text
        assert "Execution Mode" in run_form.text
        assert "Model" in run_form.text

        create = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "model": "gemini-2.5-pro",
                "input__prompt": "hello",
                "parameter__top_k": "3",
                "runtime__no_cache": "on",
                "runtime__debug": "on",
                "runtime__session_timeout_sec": "900",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert create.headers.get("location") == "/runs/req-e2e-1"
        assert fake_backend.create_payloads[-1]["runtime_options"]["execution_mode"] == "auto"
        assert fake_backend.create_payloads[-1]["model"] == "gemini-2.5-pro"
        assert fake_backend.create_payloads[-1]["runtime_options"]["no_cache"] is True
        assert fake_backend.create_payloads[-1]["runtime_options"]["debug"] is True
        assert fake_backend.create_payloads[-1]["runtime_options"]["session_timeout_sec"] == 900

        runs = await _request(app, "GET", "/runs")
        assert runs.status_code == 200
        assert "Open Observation" in runs.text
        assert "/runs/req-e2e-1" in runs.text

        recordings_redirect = await _request(app, "GET", "/recordings", follow_redirects=False)
        assert recordings_redirect.status_code == 307
        assert recordings_redirect.headers.get("location") == "/runs"

        state = await _request(app, "GET", "/api/runs/req-e2e-1")
        assert state.status_code == 200
        assert state.json()["status"] == "waiting_user"

        pending = await _request(app, "GET", "/api/runs/req-e2e-1/pending")
        assert pending.status_code == 200
        assert pending.json()["pending"]["interaction_id"] == 7

        reply = await _request(
            app,
            "POST",
            "/api/runs/req-e2e-1/reply",
            json={"interaction_id": 7, "response": {"text": "continue"}},
        )
        assert reply.status_code == 200
        assert reply.json()["accepted"] is True
        assert fake_backend.reply_payloads[-1]["interaction_id"] == 7

        events = await _request(app, "GET", "/api/runs/req-e2e-1/events")
        assert events.status_code == 200
        assert "event: stdout" in events.text

        result = await _request(app, "GET", "/runs/req-e2e-1/result")
        assert result.status_code == 200
        assert "artifacts/out.txt" in result.text
        assert "Run File Tree (Read-only)" in result.text
        assert "result.json" in result.text

        preview = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/bundle/file?path=result/result.json",
        )
        assert preview.status_code == 200
        assert preview.json()["preview"]["mode"] == "text"
        assert '"answer":"ok"' in preview.json()["preview"]["content"]

        preview_partial = await _request(
            app,
            "GET",
            "/runs/req-e2e-1/bundle/view?path=result/result.json",
        )
        assert preview_partial.status_code == 200
        assert "result/result.json" in preview_partial.text
        assert "answer" in preview_partial.text

        recording = await _request(app, "GET", "/api/recordings/req-e2e-1")
        assert recording.status_code == 200
        steps = recording.json()["steps"]
        actions = [item["action"] for item in steps]
        assert "create_run" in actions
        assert "upload" in actions
        assert "reply" in actions
        assert "result_read" in actions
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_rejects_invalid_execution_mode(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    app.dependency_overrides[get_backend_client] = lambda: fake_backend
    try:
        response = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "gemini",
                "execution_mode": "unsupported-mode",
                "input__prompt": "hello",
                "parameter__top_k": "3",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "is not allowed for this skill" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_rejects_invalid_model_for_engine(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    app.dependency_overrides[get_backend_client] = lambda: fake_backend
    try:
        response = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "model": "not-exist-model",
                "input__prompt": "hello",
                "parameter__top_k": "3",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "is not available for selected engine" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_uses_effective_engines_when_declared_engines_empty(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackendEffectiveEnginesOnly()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    app.dependency_overrides[get_backend_client] = lambda: fake_backend
    try:
        home = await _request(app, "GET", "/")
        assert home.status_code == 200
        assert "gemini" in home.text

        run_form = await _request(app, "GET", "/skills/demo-skill/run")
        assert run_form.status_code == 200
        assert 'option value="gemini"' in run_form.text

        create = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "execution_mode": "auto",
                "model": "gemini-2.5-pro",
                "input__prompt": "hello",
                "parameter__top_k": "3",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert fake_backend.create_payloads[-1]["engine"] == "gemini"
    finally:
        app.dependency_overrides.clear()
