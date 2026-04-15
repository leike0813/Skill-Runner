from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from server.runtime.adapter.types import EngineRunResult
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionService,
)
from server.services.orchestration.run_attempt_preparation_service import RunAttemptContext
from server.services.orchestration.run_job_lifecycle_service import RunJobRequest


class _TrustRecorder:
    def __init__(self) -> None:
        self.register_calls: list[tuple[str, Path]] = []
        self.remove_calls: list[tuple[str, Path]] = []

    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        self.register_calls.append((engine, run_dir))

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        self.remove_calls.append((engine, run_dir))


class _AdapterWithLiveEmitter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        skill: Any,
        input_data: dict[str, dict[str, Any]],
        run_dir: Path,
        options: dict[str, Any],
        *,
        live_runtime_emitter: Any,
    ) -> EngineRunResult:
        self.calls.append(
            {
                "skill": skill,
                "input_data": input_data,
                "run_dir": run_dir,
                "options": dict(options),
                "live_runtime_emitter": live_runtime_emitter,
            }
        )
        return EngineRunResult(
            exit_code=0,
            raw_stdout="stdout",
            raw_stderr="stderr",
            runtime_warnings=[{"code": "WARN", "detail": "detail"}],
            failure_reason=None,
            auth_signal_snapshot={
                "required": True,
                "confidence": "high",
            },
        )


class _AdapterWithoutLiveEmitter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(
        self,
        skill: Any,
        input_data: dict[str, dict[str, Any]],
        run_dir: Path,
        options: dict[str, Any],
    ) -> EngineRunResult:
        self.calls.append(
            {
                "skill": skill,
                "input_data": input_data,
                "run_dir": run_dir,
                "options": dict(options),
            }
        )
        return EngineRunResult(
            exit_code=9,
            raw_stdout="no-emitter-stdout",
            raw_stderr="no-emitter-stderr",
            failure_reason="TIMEOUT",
        )


class _AdapterRaises:
    async def run(self, *_args: Any, **_kwargs: Any) -> EngineRunResult:
        raise RuntimeError("adapter boom")


def _build_context(tmp_path: Path, *, adapter: Any) -> RunAttemptContext:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunAttemptContext(
        request=RunJobRequest(
            run_id="run-1",
            skill_id="skill-1",
            engine_name="codex",
            options={"execution_mode": "auto"},
        ),
        run_dir=run_dir,
        request_record={"request_id": "req-1"},
        request_id="req-1",
        execution_mode="auto",
        conversation_mode="session",
        session_capable=True,
        is_interactive=False,
        interactive_auto_reply=False,
        can_wait_for_user=False,
        can_persist_waiting_user=False,
        interactive_profile=None,
        attempt_number=2,
        skill=object(),
        adapter=adapter,
        input_data={"input": {"foo": "bar"}, "parameter": {"x": 1}},
        run_options={
            "__run_id": "run-1",
            "__attempt_number": 2,
            "__request_id": "req-1",
            "__engine_name": "codex",
        },
        custom_provider_model=None,
    )


@pytest.mark.asyncio
async def test_execute_uses_live_runtime_emitter_when_adapter_accepts_it(tmp_path: Path) -> None:
    trust = _TrustRecorder()
    adapter = _AdapterWithLiveEmitter()
    consumed_handles: list[str] = []

    async def _consume(handle_id: str) -> dict[str, Any]:
        consumed_handles.append(handle_id)
        return {"status": "stored"}

    context = _build_context(tmp_path, adapter=adapter)
    result = await RunAttemptExecutionService().execute(
        context=context,
        trust_manager_backend=trust,
        run_handle_consumer=_consume,
    )

    assert len(adapter.calls) == 1
    assert "live_runtime_emitter" in adapter.calls[0]
    assert trust.register_calls == [("codex", context.run_dir)]
    assert trust.remove_calls == [("codex", context.run_dir)]
    await adapter.calls[0]["live_runtime_emitter"]._run_handle_consumer("thread-1")
    assert consumed_handles == ["thread-1"]
    assert result.process_exit_code == 0
    assert result.process_raw_stdout == "stdout"
    assert result.process_raw_stderr == "stderr"
    assert result.runtime_execution_warnings == [{"code": "WARN", "detail": "detail"}]
    assert result.auth_signal_snapshot == {"required": True, "confidence": "high"}
    assert result.run_handle_consumer is _consume


@pytest.mark.asyncio
async def test_execute_omits_live_runtime_emitter_for_legacy_adapter(tmp_path: Path) -> None:
    trust = _TrustRecorder()
    adapter = _AdapterWithoutLiveEmitter()

    async def _consume(handle_id: str) -> dict[str, Any]:
        return {"status": handle_id}

    context = _build_context(tmp_path, adapter=adapter)
    result = await RunAttemptExecutionService().execute(
        context=context,
        trust_manager_backend=trust,
        run_handle_consumer=_consume,
    )

    assert len(adapter.calls) == 1
    assert "live_runtime_emitter" not in adapter.calls[0]
    assert trust.register_calls == [("codex", context.run_dir)]
    assert trust.remove_calls == [("codex", context.run_dir)]
    assert result.process_exit_code == 9
    assert result.process_failure_reason == "TIMEOUT"
    assert result.process_raw_stdout == "no-emitter-stdout"
    assert result.process_raw_stderr == "no-emitter-stderr"
    assert result.runtime_execution_warnings == []


@pytest.mark.asyncio
async def test_execute_cleans_up_trust_on_adapter_exception(tmp_path: Path) -> None:
    trust = _TrustRecorder()
    context = _build_context(tmp_path, adapter=_AdapterRaises())

    async def _consume(handle_id: str) -> dict[str, Any]:
        return {"status": handle_id}

    with pytest.raises(RuntimeError, match="adapter boom"):
        await RunAttemptExecutionService().execute(
            context=context,
            trust_manager_backend=trust,
            run_handle_consumer=_consume,
        )

    assert trust.register_calls == [("codex", context.run_dir)]
    assert trust.remove_calls == [("codex", context.run_dir)]
