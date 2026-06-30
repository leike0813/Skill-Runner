from __future__ import annotations

from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import KiloExecutionAdapter


class KiloCommandBuilder:
    def __init__(self, adapter: "KiloExecutionAdapter") -> None:
        self._adapter = adapter

    def _resolve_kilo_command(self) -> str:
        return str(self._adapter._resolve_kilo_command())

    def _model_args(self, options: dict[str, object]) -> list[str]:
        model_obj = options.get("runtime_model")
        if not isinstance(model_obj, str) or not model_obj.strip():
            model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            return ["--model", model_obj.strip()]
        return []

    def _apply_run_dir_args(
        self,
        default_flags: list[str],
        ctx: AdapterExecutionContext | None,
    ) -> list[str]:
        run_dir_flag = self._adapter.profile.launch.run_dir_flag
        if ctx is None or not isinstance(run_dir_flag, str) or not run_dir_flag:
            return default_flags
        run_dir_args = [run_dir_flag, str(ctx.run_dir)]
        if default_flags and default_flags[0] == "run":
            return [default_flags[0], *run_dir_args, *default_flags[1:]]
        return [*run_dir_args, *default_flags]

    def build_start_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        ctx: AdapterExecutionContext | None = None,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        executable = self._resolve_kilo_command()
        if passthrough_args is not None:
            return [executable, *passthrough_args]
        default_flags = (
            list(self._adapter.profile.command_defaults.start)
            if use_profile_defaults
            else ["run", "--format", "json", "--auto"]
        )
        default_flags = self._apply_run_dir_args(default_flags, ctx)
        return [executable, *default_flags, *self._model_args(options), prompt]

    def build_start(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
    ) -> list[str]:
        return self.build_start_with_options(prompt=prompt, options=ctx.options, ctx=ctx)

    def build_resume_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        session_handle: EngineSessionHandle,
        ctx: AdapterExecutionContext | None = None,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        executable = self._resolve_kilo_command()
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty kilo session id")
        if passthrough_args is not None:
            return [executable, *passthrough_args]
        default_flags = (
            list(self._adapter.profile.command_defaults.resume)
            if use_profile_defaults
            else ["run", "--format", "json", "--auto", "--session"]
        )
        default_flags = self._apply_run_dir_args(default_flags, ctx)
        return [executable, *default_flags, session_id, *self._model_args(options), prompt]

    def build_resume(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
        session_handle: EngineSessionHandle,
    ) -> list[str]:
        return self.build_resume_with_options(
            prompt=prompt,
            options=ctx.options,
            session_handle=session_handle,
            ctx=ctx,
        )
