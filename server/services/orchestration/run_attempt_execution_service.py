from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from server.runtime.protocol.live_publish import LiveRuntimeEmitterImpl

from .run_attempt_preparation_service import RunAttemptContext

logger = logging.getLogger(__name__)


def _adapter_accepts_live_runtime_emitter(adapter: Any) -> bool:
    run_callable = getattr(adapter, "run", None)
    if run_callable is None:
        return False
    try:
        signature = inspect.signature(run_callable)
    except (TypeError, ValueError):
        return False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == "live_runtime_emitter":
            return True
    return False


@dataclass
class RunAttemptExecutionResult:
    engine_result: Any
    process_exit_code: int | None
    process_failure_reason: str | None
    process_raw_stdout: str
    process_raw_stderr: str
    runtime_execution_warnings: list[dict[str, str]]
    adapter_stream_parser: Any
    auth_signal_snapshot: dict[str, Any] | None
    run_handle_consumer: Callable[[str], Awaitable[dict[str, Any]]]
    live_runtime_emitter_factory: Callable[[], Any]


class RunAttemptExecutionService:
    async def execute(
        self,
        *,
        context: RunAttemptContext,
        trust_manager_backend: Any,
        run_handle_consumer: Callable[[str], Awaitable[dict[str, Any]]],
    ) -> RunAttemptExecutionResult:
        adapter = context.adapter
        run_id = context.request.run_id
        engine_name = context.request.engine_name
        adapter_stream_parser = getattr(adapter, "stream_parser", adapter)
        live_runtime_emitter = LiveRuntimeEmitterImpl(
            run_id=run_id,
            run_dir=context.run_dir,
            engine=engine_name,
            attempt_number=context.attempt_number,
            stream_parser=adapter_stream_parser,
            run_handle_consumer=run_handle_consumer,
        )

        trust_manager_backend.register_run_folder(engine_name, context.run_dir)
        try:
            logger.info(
                "run_attempt_execute_begin run_id=%s request_id=%s attempt=%s engine=%s",
                run_id,
                context.request_id,
                context.attempt_number,
                engine_name,
            )
            if _adapter_accepts_live_runtime_emitter(adapter):
                result = await adapter.run(
                    context.skill,
                    context.input_data,
                    context.run_dir,
                    context.run_options,
                    live_runtime_emitter=live_runtime_emitter,
                )
            else:
                result = await adapter.run(
                    context.skill,
                    context.input_data,
                    context.run_dir,
                    context.run_options,
                )
        finally:
            try:
                trust_manager_backend.remove_run_folder(engine_name, context.run_dir)
            except (OSError, RuntimeError, ValueError):
                logger.warning(
                    "Failed to cleanup run folder trust for engine=%s run_id=%s",
                    engine_name,
                    run_id,
                    exc_info=True,
                )

        return RunAttemptExecutionResult(
            engine_result=result,
            process_exit_code=getattr(result, "exit_code", None),
            process_failure_reason=getattr(result, "failure_reason", None),
            process_raw_stdout=getattr(result, "raw_stdout", "") or "",
            process_raw_stderr=getattr(result, "raw_stderr", "") or "",
            runtime_execution_warnings=(
                [
                    dict(item)
                    for item in getattr(result, "runtime_warnings", [])
                    if isinstance(item, dict)
                ]
                if isinstance(getattr(result, "runtime_warnings", None), list)
                else []
            ),
            adapter_stream_parser=adapter_stream_parser,
            auth_signal_snapshot=(
                {
                    str(key): value
                    for key, value in getattr(result, "auth_signal_snapshot", {}).items()
                }
                if isinstance(getattr(result, "auth_signal_snapshot", None), dict)
                else None
            ),
            run_handle_consumer=run_handle_consumer,
            live_runtime_emitter_factory=lambda: LiveRuntimeEmitterImpl(
                run_id=run_id,
                run_dir=context.run_dir,
                engine=engine_name,
                attempt_number=context.attempt_number,
                stream_parser=adapter_stream_parser,
                run_handle_consumer=run_handle_consumer,
            ),
        )
