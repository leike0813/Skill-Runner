from __future__ import annotations

from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.orchestration.engine_command_profile import merge_cli_args

if TYPE_CHECKING:
    from .execution_adapter import GeminiExecutionAdapter


class GeminiCommandBuilder:
    def __init__(self, adapter: "GeminiExecutionAdapter") -> None:
        self._adapter = adapter

    def build_start_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        gemini_cmd = self._adapter.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        effective_passthrough = passthrough_args
        if effective_passthrough is None:
            raw = options.get("__passthrough_cli_args")
            if isinstance(raw, list):
                effective_passthrough = [str(item) for item in raw]
        if effective_passthrough is not None:
            return [str(gemini_cmd), *effective_passthrough]
        defaults = self._adapter._resolve_profile_flags(  # noqa: SLF001
            action="start",
            use_profile_defaults=use_profile_defaults,
        )
        flags = merge_cli_args(defaults, [])
        return [str(gemini_cmd), *flags, prompt]

    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:
        use_profile_defaults = bool(ctx.options.get("__use_profile_defaults", True))
        return self.build_start_with_options(
            prompt=prompt,
            options=ctx.options,
            use_profile_defaults=use_profile_defaults,
        )

    def build_resume_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        session_handle: EngineSessionHandle,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty gemini session_id")
        gemini_cmd = self._adapter.agent_manager.resolve_engine_command("gemini")
        if gemini_cmd is None:
            raise RuntimeError("Gemini CLI not found in managed prefix")
        effective_passthrough = passthrough_args
        if effective_passthrough is None:
            raw = options.get("__passthrough_cli_args")
            if isinstance(raw, list):
                effective_passthrough = [str(item) for item in raw]
        if effective_passthrough is not None:
            flags = [
                token
                for token in effective_passthrough
                if isinstance(token, str) and token.startswith("-")
            ]
            merged = merge_cli_args([], flags)
            return [str(gemini_cmd), "--resume", session_id, *merged, prompt]
        defaults = self._adapter._resolve_profile_flags(  # noqa: SLF001
            action="resume",
            use_profile_defaults=use_profile_defaults,
        )
        merged = merge_cli_args(defaults, [])
        return [str(gemini_cmd), "--resume", session_id, *merged, prompt]

    def build_resume(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
        session_handle: EngineSessionHandle,
    ) -> list[str]:
        use_profile_defaults = bool(ctx.options.get("__use_profile_defaults", True))
        return self.build_resume_with_options(
            prompt=prompt,
            options=ctx.options,
            session_handle=session_handle,
            use_profile_defaults=use_profile_defaults,
        )
