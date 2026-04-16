from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.runtime.adapter.types import EngineRunResult
from server.runtime.auth_detection.types import AuthDetectionResult
from server.services.orchestration.run_audit_service import RunAuditService
from server.services.orchestration.run_attempt_outcome_service import (
    resolve_structured_output_candidate,
)
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)
from server.services.orchestration.run_output_convergence_service import (
    WARNING_OUTPUT_SCHEMA_REPAIR_SKIPPED_NO_SESSION_HANDLE,
    run_output_convergence_service,
)
from server.services.orchestration.run_output_schema_service import run_output_schema_service


class _HandleStore:
    def __init__(self, handle: dict[str, object] | None = None):
        self.handle = handle

    async def get_engine_session_handle(self, request_id: str) -> dict[str, object] | None:
        _ = request_id
        return self.handle


class _FakeRepairAdapter:
    def __init__(self, rerun_outputs: list[str]) -> None:
        self._rerun_outputs = list(rerun_outputs)
        self.repair_run_count = 0

    async def run(self, skill, input_data, run_dir, options, live_runtime_emitter=None):
        _ = skill
        _ = input_data
        _ = run_dir
        _ = live_runtime_emitter
        assert options.get("__repair_round_index", 0) >= 1
        self.repair_run_count += 1
        raw_stdout = self._rerun_outputs.pop(0)
        return EngineRunResult(
            exit_code=0,
            raw_stdout=raw_stdout,
            raw_stderr="",
            artifacts_created=[],
        )

    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
        _ = stderr_raw
        _ = pty_raw
        text = stdout_raw.decode("utf-8", errors="replace")
        return {
            "parser": "test",
            "confidence": 1.0,
            "session_id": "thread-1",
            "assistant_messages": [{"text": text}] if text else [],
            "raw_rows": [],
            "diagnostics": [],
            "structured_types": [],
        }

    def parse_json_with_deterministic_repair(self, text: str):
        stripped = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", stripped, re.IGNORECASE)
        candidate = fenced.group(1) if fenced is not None else stripped
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                repair_level = "deterministic_generic" if fenced is not None else "none"
                return payload, repair_level
        return None, "none"


def _build_skill(tmp_path: Path, *, interactive: bool = False) -> SkillManifest:
    skill_dir = tmp_path / ("skill-interactive" if interactive else "skill-auto")
    skill_dir.mkdir()
    (skill_dir / "input.schema.json").write_text(json.dumps({"type": "object", "properties": {}}), encoding="utf-8")
    (skill_dir / "parameter.schema.json").write_text(json.dumps({"type": "object", "properties": {}}), encoding="utf-8")
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
        id="test-skill-interactive" if interactive else "test-skill-auto",
        path=skill_dir,
        execution_modes=["interactive"] if interactive else ["auto"],
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        },
    )


def _auth_result() -> AuthDetectionResult:
    return AuthDetectionResult(
        classification="unknown",
        subcategory=None,
        confidence="low",
        engine="codex",
        evidence_sources=[],
        details={},
    )


def _append_orchestrator_event(audit_service: RunAuditService):
    def _append(*, run_dir, attempt_number, category, type_name, data, engine_name=None):
        _ = engine_name
        audit_service.append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category=category,
            type_name=type_name,
            data=data,
        )

    return _append


@pytest.mark.asyncio
async def test_convergence_repairs_auto_attempt_with_fenced_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path)
    run_output_schema_service.materialize(skill=skill, execution_mode="auto", run_dir=run_dir)
    adapter = _FakeRepairAdapter(
        ['```json\n{"__SKILL_DONE__": true, "value": "fixed"}\n```']
    )
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    initial_result = EngineRunResult(exit_code=0, raw_stdout="not-json", raw_stderr="", artifacts_created=[])

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(
            EngineSessionHandle(
                engine="codex",
                handle_type=EngineSessionHandleType.SESSION_ID,
                handle_value="thread-1",
                created_at_turn=1,
            ).model_dump(mode="json")
        ),
        run_id="run-1",
        engine_name="codex",
        execution_mode="auto",
        attempt_number=1,
        options={},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(stdout_raw=b"not-json", stderr_raw=b""),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "converged"
    assert result.output_data == {"value": "fixed"}
    assert result.branch_resolved == "final"
    assert adapter.repair_run_count == 1
    repair_rows = [
        json.loads(line)
        for line in (run_dir / ".audit" / "output_repair.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    orchestrator_rows = [
        json.loads(line)
        for line in (run_dir / ".audit" / "orchestrator_events.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert repair_rows[0]["deterministic_repair_applied"] is True
    assert repair_rows[0]["deterministic_repair_succeeded"] is True
    assert repair_rows[0]["schema_valid"] is True
    superseded = next(row for row in orchestrator_rows if row["type"] == "assistant.message.superseded")
    assert superseded["data"]["message_id"].startswith("m_1_")
    assert superseded["data"]["message_family_id"] == superseded["data"]["message_id"]
    assert superseded["data"]["repair_round_index"] == 1


@pytest.mark.asyncio
async def test_convergence_skips_repair_without_session_handle(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path)
    run_output_schema_service.materialize(skill=skill, execution_mode="auto", run_dir=run_dir)
    adapter = _FakeRepairAdapter([])
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    initial_result = EngineRunResult(exit_code=0, raw_stdout="still not json", raw_stderr="", artifacts_created=[])

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(None),
        run_id="run-1",
        engine_name="codex",
        execution_mode="auto",
        attempt_number=1,
        options={},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(stdout_raw=b"still not json", stderr_raw=b""),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "skipped"
    assert WARNING_OUTPUT_SCHEMA_REPAIR_SKIPPED_NO_SESSION_HANDLE in result.validation_warnings
    assert adapter.repair_run_count == 0
    repair_rows = [
        json.loads(line)
        for line in (run_dir / ".audit" / "output_repair.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert repair_rows[0]["outcome"] == "skipped"


@pytest.mark.asyncio
async def test_convergence_repairs_interactive_attempt_to_pending_branch(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path, interactive=True)
    run_output_schema_service.materialize(skill=skill, execution_mode="interactive", run_dir=run_dir)
    adapter = _FakeRepairAdapter(
        ['```json\n{"__SKILL_DONE__": false, "message": "Need your choice", "ui_hints": {"kind": "choose_one", "options": [{"label": "A", "value": "a"}]}}\n```']
    )
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    initial_result = EngineRunResult(exit_code=0, raw_stdout="<ASK_USER_YAML>legacy</ASK_USER_YAML>", raw_stderr="", artifacts_created=[])

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(
            EngineSessionHandle(
                engine="codex",
                handle_type=EngineSessionHandleType.SESSION_ID,
                handle_value="thread-1",
                created_at_turn=1,
            ).model_dump(mode="json")
        ),
        run_id="run-1",
        engine_name="codex",
        execution_mode="interactive",
        attempt_number=1,
        options={},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(
            stdout_raw=b"<ASK_USER_YAML>legacy</ASK_USER_YAML>",
            stderr_raw=b"",
        ),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "converged"
    assert result.branch_resolved == "pending"
    assert result.pending_interaction_candidate is not None
    assert result.pending_interaction_candidate["prompt"] == "Need your choice"
    assert result.pending_interaction_candidate["interaction_id"] == 1


@pytest.mark.asyncio
async def test_convergence_canonicalizes_codex_compat_final_before_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path, interactive=True)
    run_output_schema_service.materialize(skill=skill, execution_mode="interactive", run_dir=run_dir)
    adapter = _FakeRepairAdapter([])
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    compat_final = '{"__SKILL_DONE__": true, "value": "done", "message": null, "ui_hints": null}'
    initial_result = EngineRunResult(
        exit_code=0,
        raw_stdout=compat_final,
        raw_stderr="",
        artifacts_created=[],
    )

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(
            EngineSessionHandle(
                engine="codex",
                handle_type=EngineSessionHandleType.SESSION_ID,
                handle_value="thread-1",
                created_at_turn=1,
            ).model_dump(mode="json")
        ),
        run_id="run-1",
        engine_name="codex",
        execution_mode="interactive",
        attempt_number=3,
        options={"execution_mode": "interactive"},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(
            stdout_raw=compat_final.encode("utf-8"),
            stderr_raw=b"",
        ),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "not_needed"
    assert result.branch_resolved == "final"
    assert result.output_data == {"value": "done"}
    assert result.pending_interaction_candidate is None
    assert result.schema_output_errors == []
    assert adapter.repair_run_count == 0
    assert not (run_dir / ".audit" / "output_repair.3.jsonl").exists()


@pytest.mark.asyncio
async def test_convergence_canonicalizes_codex_compat_pending_before_validation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path, interactive=True)
    run_output_schema_service.materialize(skill=skill, execution_mode="interactive", run_dir=run_dir)
    adapter = _FakeRepairAdapter([])
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    compat_pending = json.dumps(
        {
            "__SKILL_DONE__": False,
            "value": None,
            "message": "Need your choice",
            "ui_hints": {
                "kind": "choose_one",
                "prompt": None,
                "hint": "Pick one.",
                "options": [{"label": "A", "value": "a"}],
                "files": None,
            },
        },
        ensure_ascii=False,
    )
    initial_result = EngineRunResult(
        exit_code=0,
        raw_stdout=compat_pending,
        raw_stderr="",
        artifacts_created=[],
    )

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(
            EngineSessionHandle(
                engine="codex",
                handle_type=EngineSessionHandleType.SESSION_ID,
                handle_value="thread-1",
                created_at_turn=1,
            ).model_dump(mode="json")
        ),
        run_id="run-1",
        engine_name="codex",
        execution_mode="interactive",
        attempt_number=3,
        options={"execution_mode": "interactive"},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(
            stdout_raw=compat_pending.encode("utf-8"),
            stderr_raw=b"",
        ),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "not_needed"
    assert result.branch_resolved == "pending"
    assert result.output_data == {}
    assert result.pending_interaction_candidate is not None
    assert result.pending_interaction_candidate["kind"] == "choose_one"
    assert result.pending_interaction_candidate["prompt"] == "Need your choice"
    assert adapter.repair_run_count == 0


@pytest.mark.asyncio
async def test_convergence_exhausted_emits_supersede_for_last_invalid_final(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = _build_skill(tmp_path)
    run_output_schema_service.materialize(skill=skill, execution_mode="auto", run_dir=run_dir)
    adapter = _FakeRepairAdapter(["still bad", "still bad again", "still bad third"])
    audit_service = RunAuditService()
    interaction_service = RunInteractionLifecycleService()
    initial_result = EngineRunResult(exit_code=0, raw_stdout="not-json", raw_stderr="", artifacts_created=[])

    result = await run_output_convergence_service.converge(
        adapter=adapter,
        skill=skill,
        input_data={"input": {}, "parameter": {}},
        run_dir=run_dir,
        request_id="req-1",
        run_store_backend=_HandleStore(
            EngineSessionHandle(
                engine="codex",
                handle_type=EngineSessionHandleType.SESSION_ID,
                handle_value="thread-1",
                created_at_turn=1,
            ).model_dump(mode="json")
        ),
        run_id="run-1",
        engine_name="codex",
        execution_mode="auto",
        attempt_number=1,
        options={},
        initial_result=initial_result,
        initial_runtime_parse_result=adapter.parse_runtime_stream(stdout_raw=b"not-json", stderr_raw=b""),
        auth_detection_result=_auth_result(),
        auth_detection_high=False,
        resolve_structured_output_candidate=resolve_structured_output_candidate,
        strip_done_marker_for_output_validation=interaction_service.strip_done_marker_for_output_validation,
        extract_pending_interaction=interaction_service.extract_pending_interaction,
        append_orchestrator_event=_append_orchestrator_event(audit_service),
        append_output_repair_record=audit_service.append_output_repair_record,
        live_runtime_emitter_factory=lambda: SimpleNamespace(),
    )

    assert result.convergence_state == "exhausted"
    orchestrator_rows = [
        json.loads(line)
        for line in (run_dir / ".audit" / "orchestrator_events.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    superseded_rows = [row for row in orchestrator_rows if row["type"] == "assistant.message.superseded"]
    assert len(superseded_rows) == 4
    assert superseded_rows[-1]["data"]["repair_round_index"] == 4
