import asyncio
import io
from pathlib import Path
from typing import Any
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from e2e_client.app import create_app
from e2e_client.backend import RUN_SOURCE_INSTALLED, RUN_SOURCE_TEMP
from e2e_client.recording import RecordingStore
from e2e_client.routes import get_backend_client, get_settings


class FakeBackend:
    def __init__(self):
        self.reply_payloads: list[dict[str, Any]] = []
        self.reply_sources: list[str] = []
        self.pending_sources: list[str] = []
        self.history_requests: list[dict[str, Any]] = []
        self.log_range_requests: list[dict[str, Any]] = []
        self.create_payloads: list[dict[str, Any]] = []
        self.temp_create_payloads: list[dict[str, Any]] = []
        self.temp_upload_payloads: list[dict[str, Any]] = []

    async def list_management_engines(self) -> dict[str, Any]:
        return {
            "engines": [
                {"engine": "gemini"},
                {"engine": "codex"},
                {"engine": "iflow"},
            ]
        }

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
        if engine != "gemini":
            return {"engine": engine, "models": []}
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

    async def create_temp_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.temp_create_payloads.append(payload)
        return {"request_id": "req-temp-1", "status": "queued"}

    async def upload_run_file(self, request_id: str, zip_bytes: bytes) -> dict[str, Any]:
        assert request_id == "req-e2e-1"
        assert zip_bytes
        return {"request_id": request_id, "cache_hit": False, "extracted_files": ["input_file"]}

    async def upload_temp_run(
        self,
        request_id: str,
        *,
        skill_package_zip: bytes,
        input_zip: bytes | None = None,
    ) -> dict[str, Any]:
        assert request_id == "req-temp-1"
        assert skill_package_zip
        skill_entries = []
        with zipfile.ZipFile(io.BytesIO(skill_package_zip), mode="r") as archive:
            skill_entries = archive.namelist()
        input_entries = []
        if input_zip is not None:
            with zipfile.ZipFile(io.BytesIO(input_zip), mode="r") as archive:
                input_entries = archive.namelist()
        self.temp_upload_payloads.append(
            {
                "request_id": request_id,
                "skill_entries": skill_entries,
                "input_entries": input_entries,
            }
        )
        return {"request_id": request_id, "cache_hit": False, "status": "queued", "extracted_files": input_entries}

    async def get_run_state(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if run_source == RUN_SOURCE_TEMP:
            return {
                "request_id": request_id,
                "run_id": "run-temp-1",
                "status": "waiting_user",
                "pending_interaction_id": 11,
                "skill_id": "demo-prime-number",
                "engine": "gemini",
            }
        return {
            "request_id": request_id,
            "run_id": "run-e2e-1",
            "status": "waiting_user",
            "pending_interaction_id": 7,
            "skill_id": "demo-skill",
            "engine": "gemini",
        }

    async def get_run_pending(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        self.pending_sources.append(run_source)
        if run_source == RUN_SOURCE_TEMP:
            return {
                "request_id": request_id,
                "status": "waiting_user",
                "pending": {
                    "interaction_id": 11,
                    "kind": "open_text",
                    "prompt": "Temp confirm",
                },
            }
        return {
            "request_id": request_id,
            "status": "waiting_user",
            "pending": {
                "interaction_id": 7,
                "kind": "open_text",
                "prompt": "Please confirm",
            },
        }

    async def post_run_reply(
        self,
        request_id: str,
        payload: dict[str, Any],
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        self.reply_payloads.append(payload)
        self.reply_sources.append(run_source)
        return {"request_id": request_id, "status": "queued", "accepted": True}

    async def get_run_result(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if run_source == RUN_SOURCE_TEMP:
            return {"request_id": request_id, "result": {"answer": "temp-ok"}}
        return {"request_id": request_id, "result": {"answer": "ok"}}

    async def get_run_artifacts(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if run_source == RUN_SOURCE_TEMP:
            return {"request_id": request_id, "artifacts": ["artifacts/temp-out.txt"]}
        return {"request_id": request_id, "artifacts": ["artifacts/out.txt"]}

    async def get_run_bundle(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> bytes:
        del request_id
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            if run_source == RUN_SOURCE_TEMP:
                archive.writestr("result/result.json", '{"answer":"temp-ok"}')
                archive.writestr("artifacts/temp-out.txt", "temp artifact text")
            else:
                archive.writestr("result/result.json", '{"answer":"ok"}')
                archive.writestr("artifacts/out.txt", "artifact text")
        return buffer.getvalue()

    async def stream_run_events(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
        cursor: int = 0,
        stdout_from: int = 0,
        stderr_from: int = 0,
    ):
        del request_id, run_source, cursor, stdout_from, stderr_from
        yield b'event: snapshot\ndata: {"status":"running"}\n\n'
        yield b'event: stdout\ndata: {"chunk":"hello"}\n\n'
        yield b'event: end\ndata: {"reason":"waiting_user"}\n\n'

    async def get_run_event_history(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
        from_seq: int | None = None,
        to_seq: int | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ) -> dict[str, Any]:
        self.history_requests.append(
            {
                "request_id": request_id,
                "run_source": run_source,
                "from_seq": from_seq,
                "to_seq": to_seq,
                "from_ts": from_ts,
                "to_ts": to_ts,
            }
        )
        return {
            "request_id": request_id,
            "events": [
                {"seq": 2, "type": "chat_event", "run_source": run_source},
            ],
        }

    async def get_run_log_range(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
        stream: str,
        byte_from: int = 0,
        byte_to: int = 0,
    ) -> dict[str, Any]:
        self.log_range_requests.append(
            {
                "request_id": request_id,
                "run_source": run_source,
                "stream": stream,
                "byte_from": byte_from,
                "byte_to": byte_to,
            }
        )
        return {
            "request_id": request_id,
            "stream": stream,
            "byte_from": byte_from,
            "byte_to": byte_to,
            "run_source": run_source,
            "content": "sample-log",
        }


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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=10.0,
    ) as client:
        return await asyncio.wait_for(client.request(method, path, **kwargs), timeout=20.0)


def _install_backend_override(app, backend: FakeBackend) -> None:
    async def _backend_override():
        return backend

    async def _settings_override():
        return app.state.settings

    app.dependency_overrides[get_backend_client] = _backend_override
    app.dependency_overrides[get_settings] = _settings_override


@pytest.mark.asyncio
async def test_e2e_example_client_full_flow(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    _install_backend_override(app, fake_backend)
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
        assert create.headers.get("location") == "/runs/req-e2e-1?source=installed"
        assert fake_backend.create_payloads[-1]["runtime_options"]["execution_mode"] == "auto"
        assert fake_backend.create_payloads[-1]["model"] == "gemini-2.5-pro"
        assert fake_backend.create_payloads[-1]["runtime_options"]["no_cache"] is True
        assert fake_backend.create_payloads[-1]["runtime_options"]["debug"] is True
        assert fake_backend.create_payloads[-1]["runtime_options"]["session_timeout_sec"] == 900

        runs = await _request(app, "GET", "/runs")
        assert runs.status_code == 200
        assert "Open Observation" in runs.text
        assert "/runs/req-e2e-1" in runs.text

        observe_page = await _request(app, "GET", "/runs/req-e2e-1?source=installed")
        assert observe_page.status_code == 200
        assert "Event Relations" in observe_page.text
        assert "Raw Ref Preview" in observe_page.text

        recordings_redirect = await _request(app, "GET", "/recordings", follow_redirects=False)
        assert recordings_redirect.status_code == 307
        assert recordings_redirect.headers.get("location") == "/runs"

        state = await _request(app, "GET", "/api/runs/req-e2e-1")
        assert state.status_code == 200
        assert state.json()["status"] == "waiting_user"

        pending = await _request(app, "GET", "/api/runs/req-e2e-1/pending")
        assert pending.status_code == 200
        assert pending.json()["pending"]["interaction_id"] == 7
        assert fake_backend.pending_sources[-1] == RUN_SOURCE_INSTALLED

        reply = await _request(
            app,
            "POST",
            "/api/runs/req-e2e-1/reply",
            json={"interaction_id": 7, "response": {"text": "continue"}},
        )
        assert reply.status_code == 200
        assert reply.json()["accepted"] is True
        assert fake_backend.reply_payloads[-1]["interaction_id"] == 7
        assert fake_backend.reply_sources[-1] == RUN_SOURCE_INSTALLED

        history = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/events/history?from_seq=2&to_seq=8",
        )
        assert history.status_code == 200
        assert history.json()["events"][0]["run_source"] == RUN_SOURCE_INSTALLED
        assert fake_backend.history_requests[-1]["from_seq"] == 2
        assert fake_backend.history_requests[-1]["to_seq"] == 8

        logs_range = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/logs/range?stream=stdout&byte_from=0&byte_to=20",
        )
        assert logs_range.status_code == 200
        assert logs_range.json()["stream"] == "stdout"
        assert logs_range.json()["run_source"] == RUN_SOURCE_INSTALLED
        assert fake_backend.log_range_requests[-1]["byte_to"] == 20

        observe_summary = await _request(
            app,
            "POST",
            "/api/runs/req-e2e-1/observe-summary",
            json={
                "cursor": 12,
                "last_chat_event": {
                    "seq": 12,
                    "type": "assistant.message.final",
                    "role": "assistant",
                    "text_preview": "hello world",
                },
                "key_events": [
                    {"seq": 10, "type": "assistant.message.final", "correlation": "abc", "confidence": 0.68}
                ],
                "raw_refs": [
                    {"stream": "stdout", "byte_from": 3, "byte_to": 30}
                ],
            },
        )
        assert observe_summary.status_code == 200
        assert observe_summary.json()["ok"] is True

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
            "/runs/req-e2e-1/bundle/view?path=result/result.json&source=installed",
        )
        assert preview_partial.status_code == 200
        assert "result/result.json" in preview_partial.text
        assert "answer" in preview_partial.text

        recording = await _request(app, "GET", "/api/recordings/req-e2e-1")
        assert recording.status_code == 200
        payload = recording.json()
        steps = payload["steps"]
        actions = [item["action"] for item in steps]
        assert "create_run" in actions
        assert "upload" in actions
        assert "reply" in actions
        assert "result_read" in actions
        assert payload["observation_summary"]["cursor"] == 12
        assert payload["observation_summary"]["raw_refs"][0]["stream"] == "stdout"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_fixture_temp_skill_flow(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    _install_backend_override(app, fake_backend)
    try:
        home = await _request(app, "GET", "/")
        assert home.status_code == 200
        assert "Fixture Skills (Temp Upload)" in home.text
        assert "demo-prime-number" in home.text

        run_form = await _request(app, "GET", "/fixtures/demo-prime-number/run")
        assert run_form.status_code == 200
        assert "Run Source:</strong> temp" in run_form.text

        create = await _request(
            app,
            "POST",
            "/fixtures/demo-prime-number/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "parameter__divisor": "3",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert create.headers.get("location") == "/runs/req-temp-1?source=temp"
        assert fake_backend.temp_create_payloads
        assert fake_backend.temp_create_payloads[-1]["runtime_options"]["execution_mode"] == "auto"
        assert fake_backend.temp_upload_payloads
        assert "demo-prime-number/SKILL.md" in fake_backend.temp_upload_payloads[-1]["skill_entries"]
        assert "input_file" in fake_backend.temp_upload_payloads[-1]["input_entries"]

        state = await _request(app, "GET", "/api/runs/req-temp-1?source=temp")
        assert state.status_code == 200
        assert state.json()["status"] == "waiting_user"

        pending = await _request(app, "GET", "/api/runs/req-temp-1/pending?source=temp")
        assert pending.status_code == 200
        assert pending.json()["pending"]["interaction_id"] == 11
        assert fake_backend.pending_sources[-1] == RUN_SOURCE_TEMP

        reply = await _request(
            app,
            "POST",
            "/api/runs/req-temp-1/reply?source=temp",
            json={"interaction_id": 11, "response": {"text": "continue temp"}},
        )
        assert reply.status_code == 200
        assert reply.json()["accepted"] is True
        assert fake_backend.reply_sources[-1] == RUN_SOURCE_TEMP

        history = await _request(
            app,
            "GET",
            "/api/runs/req-temp-1/events/history?source=temp&from_seq=1",
        )
        assert history.status_code == 200
        assert history.json()["events"][0]["run_source"] == RUN_SOURCE_TEMP

        logs_range = await _request(
            app,
            "GET",
            "/api/runs/req-temp-1/logs/range?source=temp&stream=stderr&byte_from=1&byte_to=8",
        )
        assert logs_range.status_code == 200
        assert logs_range.json()["run_source"] == RUN_SOURCE_TEMP

        result = await _request(app, "GET", "/runs/req-temp-1/result?source=temp")
        assert result.status_code == 200
        assert "artifacts/temp-out.txt" in result.text

        recording = await _request(app, "GET", "/api/recordings/req-temp-1")
        assert recording.status_code == 200
        payload = recording.json()
        assert payload["run_source"] == "temp"
        actions = [item["action"] for item in payload["steps"]]
        assert "create_temp_run" in actions
        assert "upload_temp_skill_package" in actions
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_fixture_fallbacks_to_management_engines_when_omitted(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    _install_backend_override(app, fake_backend)
    try:
        run_form = await _request(app, "GET", "/fixtures/demo-auto-skill/run")
        assert run_form.status_code == 200
        assert 'option value="gemini"' in run_form.text
        assert 'option value="codex"' in run_form.text
        assert "gemini-2.5-pro" in run_form.text

        create = await _request(
            app,
            "POST",
            "/fixtures/demo-auto-skill/run",
            data={"execution_mode": "auto"},
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert fake_backend.temp_create_payloads
        assert fake_backend.temp_create_payloads[-1]["engine"] == "gemini"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_rejects_invalid_execution_mode(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    _install_backend_override(app, fake_backend)
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
    _install_backend_override(app, fake_backend)
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
    _install_backend_override(app, fake_backend)
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


@pytest.mark.asyncio
async def test_e2e_example_client_rejects_non_object_observe_summary_payload(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    app.state.recording_store = RecordingStore(tmp_path / "recordings")
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(
            app,
            "POST",
            "/api/runs/req-e2e-1/observe-summary",
            content="[]",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert "summary payload must be an object" in response.text
    finally:
        app.dependency_overrides.clear()
