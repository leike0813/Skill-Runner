from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from server.models import EngineInteractiveProfile, SkillManifest
from server.services.orchestration.run_attempt_preparation_service import (
    RunAttemptPreparationService,
    load_skill_from_run_dir,
)
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


def _build_skill(tmp_path: Path) -> SkillManifest:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "input.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"paper_path": {"type": "string"}},
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "additionalProperties": True}),
        encoding="utf-8",
    )
    (skill_dir / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    return SkillManifest(
        id="prep-skill",
        path=skill_dir,
        execution_modes=["interactive"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
    )


class _FakeRunStore:
    def __init__(
        self,
        *,
        request_record: dict[str, Any] | None,
    ) -> None:
        self.request_record = request_record

    async def get_request_by_run_id(self, _run_id: str) -> dict[str, Any] | None:
        return self.request_record


class _FakeWorkspace:
    def __init__(self, run_dir: Path | None) -> None:
        self.run_dir = run_dir

    def get_run_dir(self, _run_id: str) -> Path | None:
        return self.run_dir


class _FakeAdapter:
    async def run(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("not used in preparation tests")


class _FakeOrchestrator:
    def __init__(
        self,
        *,
        run_store: _FakeRunStore,
        workspace: _FakeWorkspace,
        adapters: dict[str, Any] | None = None,
        attempt_number: int = 1,
        interactive_profile: EngineInteractiveProfile | None = None,
    ) -> None:
        self._run_store = run_store
        self._workspace = workspace
        self.adapters = adapters or {"claude": _FakeAdapter()}
        self.attempt_number = attempt_number
        self.interactive_profile = interactive_profile or EngineInteractiveProfile(
            session_timeout_sec=321
        )
        self.inject_resume_calls: list[dict[str, Any]] = []

    def _run_store_backend(self) -> _FakeRunStore:
        return self._run_store

    def _workspace_backend(self) -> _FakeWorkspace:
        return self._workspace

    def _resolve_interactive_auto_reply(
        self,
        *,
        options: dict[str, Any],
        request_record: dict[str, Any],
    ) -> bool:
        _ = request_record
        return bool(options.get("interactive_auto_reply", False))

    async def _resolve_attempt_number(
        self,
        *,
        request_id: str | None,
        is_interactive: bool,
    ) -> int:
        _ = request_id, is_interactive
        return self.attempt_number

    async def _resolve_interactive_profile(
        self,
        request_id: str,
        engine_name: str,
        options: dict[str, Any],
    ) -> EngineInteractiveProfile:
        _ = request_id, engine_name, options
        return self.interactive_profile

    async def inject_interactive_resume_context(
        self,
        *,
        request_id: str,
        profile: EngineInteractiveProfile,
        options: dict[str, Any],
        run_dir: Path,
        run_store_backend: Any | None = None,
        append_internal_schema_warning: Any | None = None,
        resolve_attempt_number: Any | None = None,
        build_reply_prompt: Any | None = None,
    ) -> None:
        _ = (
            run_store_backend,
            append_internal_schema_warning,
            resolve_attempt_number,
            build_reply_prompt,
        )
        self.inject_resume_calls.append(
            {
                "request_id": request_id,
                "profile": profile,
                "options": dict(options),
                "run_dir": run_dir,
            }
        )

    def _load_skill_from_run_dir(
        self,
        *,
        run_dir: Path,
        skill_id: str,
        engine_name: str,
    ) -> SkillManifest | None:
        _ = run_dir, skill_id, engine_name
        return None


@pytest.mark.asyncio
async def test_prepare_builds_interactive_context_and_run_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    skill = _build_skill(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "server.services.orchestration.run_attempt_preparation_service.run_folder_git_initializer.ensure_git_repo",
        lambda _run_dir: None,
    )
    run_store = _FakeRunStore(
        request_record={
            "request_id": "req-1",
            "input": {"paper_path": "uploads/paper.pdf"},
            "parameter": {"topic": "llm"},
            "client_metadata": {"conversation_mode": "session"},
            "runtime_options": {"execution_mode": "interactive"},
        }
    )
    orchestrator = _FakeOrchestrator(
        run_store=run_store,
        workspace=_FakeWorkspace(run_dir),
        attempt_number=3,
    )
    request = RunJobRequest(
        run_id="run-1",
        skill_id=skill.id,
        engine_name="claude",
        options={"execution_mode": "interactive", "__resume_ticket_id": "ticket-1"},
        skill_override=skill,
    )

    context = await RunAttemptPreparationService().prepare(
        orchestrator=orchestrator,
        request=request,
        run_dir=run_dir,
        request_record=run_store.request_record,
        request_id="req-1",
        execution_mode="interactive",
        conversation_mode="session",
        session_capable=True,
        is_interactive=True,
        interactive_auto_reply=False,
        can_wait_for_user=True,
        can_persist_waiting_user=True,
        interactive_profile=orchestrator.interactive_profile,
        attempt_number=3,
        resolve_custom_provider_model=lambda **_kwargs: None,
        run_store_backend=run_store,
        interaction_service=orchestrator,
        audit_service=type(
            "_Audit",
            (),
            {"append_internal_schema_warning": staticmethod(lambda **_kwargs: None)},
        )(),
        resolve_attempt_number=orchestrator._resolve_attempt_number,
        build_reply_prompt=lambda response: str(response),
    )

    assert context.run_dir == run_dir
    assert context.request_id == "req-1"
    assert context.execution_mode == "interactive"
    assert context.is_interactive is True
    assert context.session_capable is True
    assert context.attempt_number == 3
    assert context.skill.id == skill.id
    assert context.input_data == {
        "input": {"paper_path": "uploads/paper.pdf"},
        "parameter": {"topic": "llm"},
    }
    assert context.run_options["__run_id"] == "run-1"
    assert context.run_options["__attempt_number"] == 3
    assert context.run_options["__request_id"] == "req-1"
    assert context.run_options["__engine_name"] == "claude"
    assert len(orchestrator.inject_resume_calls) == 1
    assert orchestrator.inject_resume_calls[0]["request_id"] == "req-1"
    assert orchestrator.inject_resume_calls[0]["run_dir"] == run_dir


@pytest.mark.asyncio
async def test_prepare_raises_on_invalid_input(tmp_path: Path) -> None:
    skill = _build_skill(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    request = RunJobRequest(
        run_id="run-invalid",
        skill_id=skill.id,
        engine_name="claude",
        options={},
        skill_override=skill,
    )
    orchestrator = _FakeOrchestrator(
        run_store=_FakeRunStore(
            request_record={
                "request_id": "req-bad",
                "input": {"unknown": "value"},
                "parameter": {},
            }
        ),
        workspace=_FakeWorkspace(run_dir),
    )

    with pytest.raises(ValueError, match="Input validation failed"):
        await RunAttemptPreparationService().prepare(
            orchestrator=orchestrator,
            request=request,
            run_dir=run_dir,
            request_record=orchestrator._run_store.request_record,
            request_id="req-bad",
            execution_mode="auto",
            conversation_mode="session",
            session_capable=True,
            is_interactive=False,
            interactive_auto_reply=False,
            can_wait_for_user=False,
            can_persist_waiting_user=False,
            interactive_profile=None,
            attempt_number=1,
            resolve_custom_provider_model=lambda **_kwargs: None,
            run_store_backend=orchestrator._run_store_backend(),
            interaction_service=orchestrator,
            audit_service=type(
                "_Audit",
                (),
                {"append_internal_schema_warning": staticmethod(lambda **_kwargs: None)},
            )(),
            resolve_attempt_number=orchestrator._resolve_attempt_number,
            build_reply_prompt=lambda response: str(response),
        )


def test_load_skill_from_run_dir_reads_workspace_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-resume"
    skill_id = "temp-resume-skill"
    skill_dir = run_dir / ".codex" / "skills" / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("demo", encoding="utf-8")
    (assets_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (assets_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}),
        encoding="utf-8",
    )
    (assets_dir / "output.schema.json").write_text(
        json.dumps({"type": "object", "properties": {"ok": {"type": "boolean"}}}),
        encoding="utf-8",
    )
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "name": "Temp Resume Skill",
                "version": "0.1.0",
                "engines": ["codex"],
                "execution_modes": ["interactive"],
                "schemas": {
                    "input": "assets/input.schema.json",
                    "parameter": "assets/parameter.schema.json",
                    "output": "assets/output.schema.json",
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_skill_from_run_dir(
        run_dir=run_dir,
        skill_id=skill_id,
        engine_name="codex",
    )
    assert manifest is not None
    assert manifest.id == skill_id
    assert manifest.path == skill_dir
