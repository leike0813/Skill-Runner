import json
from pathlib import Path
from typing import Any

import pytest

from server.models import EngineInteractiveProfile, EngineSessionHandle, EngineSessionHandleType
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


class _AdapterWithSessionHandle:
    def extract_session_handle(self, raw_stdout: str, turn_index: int):
        _ = raw_stdout
        return EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value=f"thread-{turn_index}",
            created_at_turn=turn_index,
        )


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

    status = await service.persist_waiting_interaction(
        adapter=_AdapterWithSessionHandle(),
        run_id="run-1",
        run_dir=run_dir,
        request_id="req-1",
        attempt_number=2,
        profile=profile,
        interactive_auto_reply=False,
        pending_interaction=pending_interaction,
        raw_runtime_output=json.dumps({"ask_user": {"prompt": "Please provide more information."}}),
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
    assert store.engine_session_handle["payload"]["handle_value"] == "thread-1"
    assert orchestrator_events
    assert orchestrator_events[0]["attempt_number"] == 2


def test_infer_pending_interaction_fallback_uses_generic_prompt() -> None:
    service = RunInteractionLifecycleService()
    pending = service.infer_pending_interaction(
        {
            "outcome": "ask_user",
            "prompt": "Long generated text with trailing meta",
            "ui_hints": {"hint": "Hint from model"},
        },
        fallback_interaction_id=3,
    )
    assert pending is not None
    assert pending["interaction_id"] == 3
    assert pending["prompt"] == "Please reply to continue."


def test_extract_pending_interaction_normalizes_single_select_alias() -> None:
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
    assert pending is not None
    assert pending["kind"] == "choose_one"
