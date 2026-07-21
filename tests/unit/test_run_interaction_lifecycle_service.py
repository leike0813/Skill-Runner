from pathlib import Path
from typing import Any

import pytest

from server.models import EngineInteractiveProfile
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)


class _CaptureStore:
    def __init__(self) -> None:
        self.pending_interaction: dict[str, Any] | None = None
        self.interactive_profile: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.engine_session_handle: dict[str, Any] | None = None
        self.current_projection: dict[str, Any] | None = None

    async def set_pending_interaction(self, request_id: str, pending_interaction: dict):
        self.pending_interaction = {"request_id": request_id, "payload": dict(pending_interaction)}

    async def set_interactive_profile(self, request_id: str, profile: dict):
        self.interactive_profile = {"request_id": request_id, "payload": dict(profile)}

    async def set_current_projection(self, request_id: str, projection: dict):
        self.current_projection = {"request_id": request_id, "payload": dict(projection)}

    async def append_interaction_history(
        self,
        *,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: dict,
        source_attempt: int,
    ):
        self.history.append(
            {
                "request_id": request_id,
                "interaction_id": interaction_id,
                "event_type": event_type,
                "payload": dict(payload),
                "source_attempt": source_attempt,
            }
        )

    async def set_engine_session_handle(self, request_id: str, handle: dict):
        self.engine_session_handle = {"request_id": request_id, "payload": dict(handle)}

    async def get_interactive_profile(self, request_id: str):
        if not self.interactive_profile or self.interactive_profile["request_id"] != request_id:
            return None
        return self.interactive_profile["payload"]

    async def get_effective_session_timeout(self, request_id: str):
        profile = await self.get_interactive_profile(request_id)
        if not isinstance(profile, dict):
            return None
        timeout_obj = profile.get("session_timeout_sec")
        return timeout_obj if isinstance(timeout_obj, int) else None

    async def get_engine_session_handle(self, request_id: str):
        if not self.engine_session_handle or self.engine_session_handle["request_id"] != request_id:
            return None
        return self.engine_session_handle["payload"]

    async def get_pending_interaction(self, request_id: str):
        if not self.pending_interaction or self.pending_interaction["request_id"] != request_id:
            return None
        return self.pending_interaction["payload"]

    async def list_interaction_history(self, request_id: str):
        return [row for row in self.history if row["request_id"] == request_id]

    async def consume_interaction_reply(self, request_id: str, interaction_id: int):
        _ = request_id
        _ = interaction_id
        return None


@pytest.mark.asyncio
async def test_persist_waiting_interaction_preserves_current_attempt_as_source_attempt(tmp_path: Path):
    service = RunInteractionLifecycleService()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    store = _CaptureStore()
    warnings = []
    orchestrator_events = []
    profile = EngineInteractiveProfile(reason="probe_ok", session_timeout_sec=900)
    pending_interaction = {
        "interaction_id": 1,
        "kind": "open_text",
        "prompt": "Please provide more information.",
        "options": [],
        "ui_hints": {},
        "default_decision_policy": "engine_judgement",
        "required_fields": [],
    }
    await store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-existing",
            "created_at_turn": 1,
        },
    )

    status = await service.persist_waiting_interaction(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        attempt_number=2,
        profile=profile,
        interactive_auto_reply=False,
        pending_interaction=pending_interaction,
        run_store_backend=store,
        append_internal_schema_warning=lambda **kwargs: warnings.append(kwargs),
        append_orchestrator_event=lambda **kwargs: orchestrator_events.append(kwargs),
    )

    assert status is None
    assert warnings == []
    assert store.pending_interaction is not None
    assert store.pending_interaction["payload"]["source_attempt"] == 2
    assert store.interactive_profile is not None
    assert store.history
    ask_user_row = store.history[0]
    assert ask_user_row["event_type"] == "ask_user"
    assert ask_user_row["source_attempt"] == 2
    assert ask_user_row["payload"]["source_attempt"] == 2
    assert store.engine_session_handle is not None
    assert store.engine_session_handle["payload"]["handle_value"] == "thread-existing"
    assert orchestrator_events
    assert orchestrator_events[0]["attempt_number"] == 2


@pytest.mark.asyncio
async def test_persist_waiting_interaction_fails_when_handle_missing(tmp_path: Path) -> None:
    service = RunInteractionLifecycleService()
    run_dir = tmp_path / "run-no-handle"
    run_dir.mkdir(parents=True, exist_ok=True)
    store = _CaptureStore()
    profile = EngineInteractiveProfile(reason="probe_ok", session_timeout_sec=900)
    pending_interaction = {
        "interaction_id": 1,
        "kind": "open_text",
        "prompt": "Please provide more information.",
        "options": [],
        "ui_hints": {},
        "default_decision_policy": "engine_judgement",
        "required_fields": [],
    }

    status = await service.persist_waiting_interaction(
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        attempt_number=1,
        profile=profile,
        interactive_auto_reply=False,
        pending_interaction=pending_interaction,
        run_store_backend=store,
        append_internal_schema_warning=lambda **kwargs: None,
        append_orchestrator_event=lambda **kwargs: None,
    )
    assert status == "SESSION_RESUME_FAILED"


def test_build_default_pending_interaction_uses_generic_prompt() -> None:
    service = RunInteractionLifecycleService()
    pending = service.build_default_pending_interaction(
        fallback_interaction_id=3,
    )
    assert pending is not None
    assert pending["interaction_id"] == 3
    assert pending["prompt"] == "Please reply to continue."
    assert pending["context"]["inferred_from"] == "legacy_waiting_fallback"


def test_extract_pending_interaction_projects_pending_branch() -> None:
    service = RunInteractionLifecycleService()
    pending = service.extract_pending_interaction(
        {
            "__SKILL_DONE__": False,
            "message": "Pick one.",
            "ui_hints": {
                "kind": "single_select",
                "options": [
                    {"label": "A", "value": "a"},
                    "Beta",
                    "  ",
                ],
            },
        },
        fallback_interaction_id=9,
    )
    assert pending is not None
    assert pending["kind"] == "choose_one"
    assert pending["prompt"] == "Pick one."
    assert pending["options"] == [
        {"label": "A", "value": "a"},
        {"label": "Beta", "value": "Beta"},
    ]


def test_extract_pending_interaction_rejects_legacy_ask_user_object() -> None:
    service = RunInteractionLifecycleService()
    pending = service.extract_pending_interaction(
        {
            "ask_user": {
                "interaction_id": 9,
                "kind": "single_select",
                "prompt": "Pick one.",
                "options": [{"label": "A", "value": "a"}],
            }
        }
    )
    assert pending is None


def test_normalize_interaction_kind_preserves_upload_files() -> None:
    service = RunInteractionLifecycleService()
    assert service.normalize_interaction_kind_name("upload_files") == "upload_files"


@pytest.mark.asyncio
async def test_resume_history_uses_public_file_projection_but_prompt_uses_private_path(tmp_path: Path) -> None:
    service = RunInteractionLifecycleService()
    store = _CaptureStore()
    await store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-1",
            "created_at_turn": 1,
        },
    )
    private = {
        "kind": "interaction_files",
        "files": [
            {
                "slot": "paper",
                "name": "paper.pdf",
                "path": "uploads/.interaction-replies/demo.1/17/token/file.pdf",
                "size_bytes": 3,
            }
        ],
    }
    public = {
        "kind": "interaction_files",
        "files": [{"slot": "paper", "name": "paper.pdf", "size_bytes": 3}],
    }
    options = {
        "__interactive_reply_payload": private,
        "__interactive_reply_observability_payload": public,
        "__interactive_reply_interaction_id": 17,
        "__interactive_source_attempt": 1,
    }
    prompt_responses: list[Any] = []

    await service.inject_interactive_resume_context(
        request_id="req-1",
        profile=EngineInteractiveProfile(reason="probe_ok", session_timeout_sec=900),
        options=options,
        run_dir=tmp_path,
        run_store_backend=store,
        append_internal_schema_warning=lambda **_kwargs: None,
        resolve_attempt_number=lambda **_kwargs: _async_value(2),
        build_reply_prompt=lambda response: prompt_responses.append(response) or "resume",
    )

    assert prompt_responses == [private]
    assert store.history[0]["payload"]["response"] == public
    assert "path" not in str(store.history[0])


async def _async_value(value: int) -> int:
    return value
