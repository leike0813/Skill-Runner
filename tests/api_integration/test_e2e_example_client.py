import asyncio
import io
import json
from pathlib import Path
from typing import Any
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from e2e_client.app import create_app
from e2e_client.backend import RUN_SOURCE_INSTALLED, RUN_SOURCE_TEMP
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
        self.service_hard_timeout_seconds = 1200

    @staticmethod
    def _is_temp_request(request_id: str) -> bool:
        return request_id == "req-temp-1"

    async def list_management_engines(self) -> dict[str, Any]:
        return {
            "engines": [
                {"engine": "gemini"},
                {"engine": "codex"},
                {"engine": "iflow"},
            ]
        }

    async def list_management_runs(self) -> dict[str, Any]:
        return {
            "runs": [
                {
                    "request_id": "req-e2e-1",
                    "run_id": "run-e2e-1",
                    "status": "waiting_user",
                    "skill_id": "demo-skill",
                    "engine": "gemini",
                    "updated_at": "2026-02-24T00:00:00",
                },
                {
                    "request_id": "req-temp-1",
                    "run_id": "run-temp-1",
                    "status": "waiting_user",
                    "skill_id": "demo-prime-number",
                    "engine": "gemini",
                    "updated_at": "2026-02-24T00:01:00",
                    "run_source": "temp",
                },
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
            "runtime": {"default_options": {"hard_timeout_seconds": 1800}},
        }

    async def get_runtime_options(self) -> dict[str, Any]:
        return {
            "service_defaults": {
                "hard_timeout_seconds": self.service_hard_timeout_seconds,
            }
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
        with zipfile.ZipFile(io.BytesIO(zip_bytes), mode="r") as archive:
            entries = sorted(archive.namelist())
        return {"request_id": request_id, "cache_hit": False, "extracted_files": entries}

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
        if self._is_temp_request(request_id):
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
        if self._is_temp_request(request_id):
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
        if self._is_temp_request(request_id):
            return {"request_id": request_id, "result": {"answer": "temp-ok"}}
        return {"request_id": request_id, "result": {"answer": "ok"}}

    async def get_run_artifacts(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if self._is_temp_request(request_id):
            return {"request_id": request_id, "artifacts": ["artifacts/temp-out.txt"]}
        return {"request_id": request_id, "artifacts": ["artifacts/out.txt"]}

    async def get_run_bundle(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> bytes:
        del run_source
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            if self._is_temp_request(request_id):
                archive.writestr("result/result.json", '{"answer":"temp-ok"}')
                archive.writestr("artifacts/temp-out.txt", "temp artifact text")
            else:
                archive.writestr("result/result.json", '{"answer":"ok"}')
                archive.writestr("artifacts/out.txt", "artifact text")
        return buffer.getvalue()

    async def get_run_files(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        del run_source
        return {
            "request_id": request_id,
            "run_id": "run-temp-1" if self._is_temp_request(request_id) else "run-e2e-1",
            "entries": [
                {"path": "result", "name": "result", "is_dir": True, "depth": 0},
                {"path": "result/result.json", "name": "result.json", "is_dir": False, "depth": 1},
            ],
        }

    async def get_run_file_preview(
        self,
        request_id: str,
        *,
        path: str,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        del run_source
        if path != "result/result.json":
            raise RuntimeError("unexpected preview path")
        answer = "temp-ok" if self._is_temp_request(request_id) else "ok"
        return {
            "request_id": request_id,
            "run_id": "run-temp-1" if self._is_temp_request(request_id) else "run-e2e-1",
            "path": path,
            "preview": {
                "mode": "text",
                "content": f'{{"answer":"{answer}"}}',
                "size": 16,
                "meta": "16 bytes, utf-8",
                "detected_format": "json",
                "rendered_html": None,
                "json_pretty": json.dumps({"answer": answer}, ensure_ascii=False, indent=2),
            },
        }

    async def stream_run_events(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
        cursor: int = 0,
    ):
        del request_id, run_source, cursor
        yield b'event: snapshot\ndata: {"status":"waiting_user","cursor":2}\n\n'
        yield (
            b'event: chat_event\ndata: {"seq":2,"type":"user.input.required",'
            b'"data":{"interaction_id":7,"kind":"open_text","prompt":"Please confirm"}}\n\n'
        )

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
        resolved_source = RUN_SOURCE_TEMP if self._is_temp_request(request_id) else RUN_SOURCE_INSTALLED
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
                {"seq": 2, "type": "chat_event", "run_source": resolved_source},
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
        resolved_source = RUN_SOURCE_TEMP if self._is_temp_request(request_id) else RUN_SOURCE_INSTALLED
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
            "run_source": resolved_source,
            "content": "sample-log",
        }

    async def get_run_final_summary(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        result_payload = await self.get_run_result(request_id, run_source=run_source)
        artifacts_payload = await self.get_run_artifacts(request_id, run_source=run_source)
        return {
            "request_id": request_id,
            "result": result_payload.get("result"),
            "artifacts": artifacts_payload.get("artifacts"),
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
            "runtime": {"default_options": {"hard_timeout_seconds": 1800}},
        }


class FakeBackendNoSkillRuntimeDefault(FakeBackend):
    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "id": "demo-skill",
            "name": "Demo Skill",
            "version": "1.0.0",
            "engines": ["gemini"],
            "execution_modes": ["auto", "interactive"],
        }


class FakeBackendFailedSummary(FakeBackend):
    async def get_run_result(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        del request_id, run_source
        return {
            "request_id": "req-e2e-failed",
            "result": {
                "status": "failed",
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "AUTH_REQUIRED: engine authentication is required or expired",
                },
            },
        }


class FakeBackendOpencode(FakeBackend):
    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "id": "demo-skill",
            "name": "Demo Skill",
            "version": "1.0.0",
            "engines": ["opencode"],
            "execution_modes": ["auto", "interactive"],
            "runtime": {"default_options": {"hard_timeout_seconds": 1800}},
        }

    async def get_engine_detail(self, engine: str) -> dict[str, Any]:
        if engine != "opencode":
            return {"engine": engine, "models": []}
        return {
            "engine": "opencode",
            "models": [
                {
                    "id": "openai/gpt-5",
                    "provider": "openai",
                    "model": "gpt-5",
                    "display_name": "OpenAI GPT-5",
                },
                {
                    "id": "anthropic/claude-sonnet-4.5",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4.5",
                    "display_name": "Claude Sonnet 4.5",
                },
            ],
        }


class FakeBackendClaudeCustomProviders(FakeBackend):
    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        assert skill_id == "demo-skill"
        return {
            "id": "demo-skill",
            "name": "Demo Skill",
            "version": "1.0.0",
            "engines": ["claude"],
            "execution_modes": ["auto", "interactive"],
            "runtime": {"default_options": {"hard_timeout_seconds": 1800}},
        }

    async def get_engine_detail(self, engine: str) -> dict[str, Any]:
        if engine != "claude":
            return {"engine": engine, "models": []}
        return {
            "engine": "claude",
            "models": [
                {
                    "id": "claude-sonnet-4-5",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "display_name": "Claude Sonnet 4.5",
                    "source": "official",
                },
                {
                    "id": "openrouter/qwen-3",
                    "provider": "openrouter",
                    "model": "qwen-3",
                    "display_name": "openrouter/qwen-3",
                    "source": "custom_provider",
                },
            ],
        }


class FakeBackendUnreachable(FakeBackend):
    async def get_run_state(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        _ = request_id, run_source
        raise httpx.ConnectError(
            "backend down",
            request=httpx.Request("GET", "http://backend.test/v1/jobs/req-unreachable"),
        )

    async def stream_run_chat(
        self,
        request_id: str,
        *,
        run_source: str = RUN_SOURCE_INSTALLED,
        cursor: int = 0,
    ):
        _ = request_id, run_source, cursor
        raise httpx.ConnectError(
            "backend down",
            request=httpx.Request("GET", "http://backend.test/v1/jobs/req-unreachable/chat"),
        )
        yield b""


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
    _install_backend_override(app, fake_backend)
    try:
        home = await _request(app, "GET", "/")
        assert home.status_code == 200
        assert "Demo Skill" in home.text
        assert "skill-mode-pill" in home.text
        assert "health-led-healthy" in home.text
        assert '<th><span class="sr-only">健康状态</span></th>' in home.text

        run_form = await _request(app, "GET", "/skills/demo-skill/run")
        assert run_form.status_code == 200
        assert "内联输入" in run_form.text
        assert "执行模式" in run_form.text
        assert "模型" in run_form.text
        assert 'name="runtime__hard_timeout_seconds"' in run_form.text
        assert 'type="number"' in run_form.text
        assert 'min="0"' in run_form.text
        assert 'step="60"' in run_form.text
        assert 'value="1800"' in run_form.text

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
                "runtime__hard_timeout_seconds": "1800",
                "runtime__no_cache": "on",
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
        assert fake_backend.create_payloads[-1]["runtime_options"]["hard_timeout_seconds"] == 1800
        assert fake_backend.create_payloads[-1]["input"]["input_file"] == "input_file/input.txt"
        assert "interactive_reply_timeout_sec" not in fake_backend.create_payloads[-1]["runtime_options"]

        runs = await _request(app, "GET", "/runs")
        assert runs.status_code == 200
        assert "详情" in runs.text
        assert "/runs/req-e2e-1" in runs.text

        observe_page = await _request(app, "GET", "/runs/req-e2e-1")
        assert observe_page.status_code == 200
        assert "待处理输入请求" in observe_page.text
        assert "Ctrl+Enter / Cmd+Enter 发送" in observe_page.text
        assert "Event Relations" not in observe_page.text
        assert "Raw Ref Preview" not in observe_page.text

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

        final_summary = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/final-summary",
        )
        assert final_summary.status_code == 200
        assert final_summary.json()["has_result"] is True
        assert final_summary.json()["has_artifacts"] is True
        assert final_summary.json()["artifacts"] == ["artifacts/out.txt"]
        assert "answer" in final_summary.json()["result_preview"]

        result = await _request(app, "GET", "/runs/req-e2e-1/result")
        assert result.status_code == 404

        preview = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/bundle/file?path=result/result.json",
        )
        assert preview.status_code == 200
        assert preview.json()["preview"]["mode"] == "text"
        assert preview.json()["preview"]["detected_format"] == "json"
        assert '"answer": "ok"' in (preview.json()["preview"]["json_pretty"] or "")

        preview_partial = await _request(
            app,
            "GET",
            "/runs/req-e2e-1/bundle/view?path=result/result.json",
        )
        assert preview_partial.status_code == 200
        assert "result/result.json" in preview_partial.text
        assert "answer" in preview_partial.text

        download = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-1/bundle/download",
        )
        assert download.status_code == 200
        assert download.headers.get("content-type", "").startswith("application/zip")
        content_disposition = download.headers.get("content-disposition", "")
        assert "attachment;" in content_disposition
        assert "req-e2e-1.bundle.zip" in content_disposition
        with zipfile.ZipFile(io.BytesIO(download.content), mode="r") as archive:
            assert "result/result.json" in archive.namelist()

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_language_query_sets_cookie_and_preserves_query():
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(app, "GET", "/runs?foo=1&bar=2&lang=fr")
        assert response.status_code == 200
        cookie_header = response.headers.get("set-cookie", "")
        assert "lang=fr" in cookie_header
        assert "Max-Age=31536000" in cookie_header
        assert "Path=/" in cookie_header

        assert "foo=1" in response.text
        assert "bar=2" in response.text
        assert "lang=ja" in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_fixture_temp_skill_flow(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        home = await _request(app, "GET", "/")
        assert home.status_code == 200
        assert "样例 Skill（临时上传）" in home.text
        assert "demo-prime-number" in home.text
        assert "<th>样例</th>" not in home.text

        run_form = await _request(app, "GET", "/fixtures/demo-prime-number/run")
        assert run_form.status_code == 200
        assert "Run 来源：</strong> temp" in run_form.text
        assert 'name="runtime__hard_timeout_seconds"' in run_form.text
        assert 'value="2400"' in run_form.text

        create = await _request(
            app,
            "POST",
            "/fixtures/demo-prime-number/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "parameter__divisor": "3",
                "runtime__hard_timeout_seconds": "2400",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert create.headers.get("location") == "/runs/req-temp-1"
        assert fake_backend.temp_create_payloads
        assert fake_backend.temp_create_payloads[-1]["runtime_options"]["execution_mode"] == "auto"
        assert fake_backend.temp_create_payloads[-1]["runtime_options"]["hard_timeout_seconds"] == 2400
        assert fake_backend.temp_create_payloads[-1]["input"]["input_file"] == "input_file/input.txt"
        assert fake_backend.temp_upload_payloads
        assert "demo-prime-number/SKILL.md" in fake_backend.temp_upload_payloads[-1]["skill_entries"]
        assert "input_file/input.txt" in fake_backend.temp_upload_payloads[-1]["input_entries"]

        state = await _request(app, "GET", "/api/runs/req-temp-1")
        assert state.status_code == 200
        assert state.json()["status"] == "waiting_user"

        pending = await _request(app, "GET", "/api/runs/req-temp-1/pending")
        assert pending.status_code == 200
        assert pending.json()["pending"]["interaction_id"] == 11
        assert fake_backend.pending_sources[-1] == RUN_SOURCE_INSTALLED

        reply = await _request(
            app,
            "POST",
            "/api/runs/req-temp-1/reply",
            json={"interaction_id": 11, "response": {"text": "continue temp"}},
        )
        assert reply.status_code == 200
        assert reply.json()["accepted"] is True
        assert fake_backend.reply_sources[-1] == RUN_SOURCE_INSTALLED

        history = await _request(
            app,
            "GET",
            "/api/runs/req-temp-1/events/history?from_seq=1",
        )
        assert history.status_code == 200
        assert history.json()["events"][0]["run_source"] == RUN_SOURCE_TEMP

        logs_range = await _request(
            app,
            "GET",
            "/api/runs/req-temp-1/logs/range?stream=stderr&byte_from=1&byte_to=8",
        )
        assert logs_range.status_code == 200
        assert logs_range.json()["run_source"] == RUN_SOURCE_TEMP

        final_summary = await _request(
            app,
            "GET",
            "/api/runs/req-temp-1/final-summary",
        )
        assert final_summary.status_code == 200
        assert final_summary.json()["has_result"] is True
        assert final_summary.json()["has_artifacts"] is True
        assert final_summary.json()["artifacts"] == ["artifacts/temp-out.txt"]

        result = await _request(app, "GET", "/runs/req-temp-1/result")
        assert result.status_code == 404

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_run_form_shows_claude_official_and_custom_provider_models():
    app = create_app()
    fake_backend = FakeBackendClaudeCustomProviders()
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(app, "GET", "/skills/demo-skill/run")
        assert response.status_code == 200
        assert "claude-sonnet-4-5" in response.text
        assert "openrouter/qwen-3" in response.text
        assert '"provider":"anthropic"' in response.text or '"provider": "anthropic"' in response.text
        assert '"provider":"openrouter"' in response.text or '"provider": "openrouter"' in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_final_summary_exposes_failed_result_status():
    app = create_app()
    fake_backend = FakeBackendFailedSummary()
    _install_backend_override(app, fake_backend)
    try:
        final_summary = await _request(
            app,
            "GET",
            "/api/runs/req-e2e-failed/final-summary",
        )
        assert final_summary.status_code == 200
        body = final_summary.json()
        assert body["result_status"] == "failed"
        assert body["result_error_code"] == "AUTH_REQUIRED"
        assert "AUTH_REQUIRED" in body["result_error_message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_fixture_fallbacks_to_management_engines_when_omitted(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        run_form = await _request(app, "GET", "/fixtures/demo-auto-skill/run")
        assert run_form.status_code == 200
        assert 'option value="gemini"' in run_form.text
        assert 'option value="codex"' in run_form.text
        assert "gemini-2.5-pro" in run_form.text
        assert 'value="1200"' in run_form.text

        create = await _request(
            app,
            "POST",
            "/fixtures/demo-auto-skill/run",
            data={
                "execution_mode": "auto",
                "runtime__hard_timeout_seconds": "1200",
            },
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
                "runtime__hard_timeout_seconds": "1800",
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
                "runtime__hard_timeout_seconds": "1800",
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
async def test_e2e_example_client_opencode_provider_model_payload(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackendOpencode()
    _install_backend_override(app, fake_backend)
    try:
        run_form = await _request(app, "GET", "/skills/demo-skill/run")
        assert run_form.status_code == 200
        assert "Provider" in run_form.text
        assert "Model" in run_form.text
        assert "openai" in run_form.text

        create = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "opencode",
                "provider": "openai",
                "model_value": "gpt-5",
                "execution_mode": "auto",
                "input__prompt": "hello",
                "parameter__top_k": "3",
                "runtime__hard_timeout_seconds": "1800",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        assert fake_backend.create_payloads[-1]["engine"] == "opencode"
        assert fake_backend.create_payloads[-1]["model"] == "openai/gpt-5"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_uses_effective_engines_when_declared_engines_empty(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackendEffectiveEnginesOnly()
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
                "runtime__hard_timeout_seconds": "1800",
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
async def test_e2e_example_client_installed_form_hard_timeout_falls_back_to_service_default():
    app = create_app()
    fake_backend = FakeBackendNoSkillRuntimeDefault()
    fake_backend.service_hard_timeout_seconds = 1260
    _install_backend_override(app, fake_backend)
    try:
        run_form = await _request(app, "GET", "/skills/demo-skill/run")
        assert run_form.status_code == 200
        assert 'name="runtime__hard_timeout_seconds"' in run_form.text
        assert 'value="1260"' in run_form.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "submitted_value",
    ["", "-60", "1.5", "abc"],
)
async def test_e2e_example_client_rejects_invalid_hard_timeout(submitted_value: str):
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "input__prompt": "hello",
                "parameter__top_k": "3",
                "runtime__hard_timeout_seconds": submitted_value,
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "hard_timeout_seconds must be a non-negative integer" in response.text
        assert not fake_backend.create_payloads
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_accepts_zero_hard_timeout():
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(
            app,
            "POST",
            "/skills/demo-skill/run",
            data={
                "engine": "gemini",
                "execution_mode": "auto",
                "input__prompt": "hello",
                "parameter__top_k": "3",
                "runtime__hard_timeout_seconds": "0",
            },
            files={
                "file__input_file": ("input.txt", b"1\n2\n3\n", "text/plain"),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert fake_backend.create_payloads[-1]["runtime_options"]["hard_timeout_seconds"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_observe_summary_route_removed(tmp_path: Path):
    app = create_app()
    fake_backend = FakeBackend()
    _install_backend_override(app, fake_backend)
    try:
        response = await _request(
            app,
            "POST",
            "/api/runs/req-e2e-1/observe-summary",
            content="[]",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_example_client_handles_backend_unreachable_for_run_api():
    app = create_app()
    fake_backend = FakeBackendUnreachable()
    _install_backend_override(app, fake_backend)
    try:
        state = await _request(app, "GET", "/api/runs/req-unreachable")
        assert state.status_code == 503
        assert state.json()["detail"] == "backend_unreachable"

        stream_res = await _request(app, "GET", "/api/runs/req-unreachable/chat")
        assert stream_res.status_code == 200
        assert "event: error" in stream_res.text
        assert "backend_unreachable" in stream_res.text
    finally:
        app.dependency_overrides.clear()
