from __future__ import annotations

import os
from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.orchestration.engine_command_profile import merge_cli_args

if TYPE_CHECKING:
    from .execution_adapter import CodexExecutionAdapter


class CodexCommandBuilder:
    def __init__(self, adapter: "CodexExecutionAdapter") -> None:
        self._adapter = adapter

    def _resolve_codex_command(self) -> str:
        return str(self._adapter._resolve_codex_command())  # noqa: SLF001

    def _apply_landlock_flag_fallback(self, flags: list[str]) -> list[str]:
        if os.environ.get("LANDLOCK_ENABLED") != "0":
            return flags
        return self._adapter._apply_landlock_flag_fallback(flags)  # noqa: SLF001

    def _strip_resume_profile_flags(self, flags: list[str]) -> list[str]:
        return self._adapter._strip_resume_profile_flags(flags)  # noqa: SLF001

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        return self._adapter._resolve_profile_flags(  # noqa: SLF001
            action=action,
            use_profile_defaults=use_profile_defaults,
        )

    def build_start_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        effective_passthrough = passthrough_args
        if effective_passthrough is None:
            raw = options.get("__passthrough_cli_args")
            if isinstance(raw, list):
                effective_passthrough = [str(item) for item in raw]
        profile_defaults = use_profile_defaults
        if "__use_profile_defaults" in options:
            profile_defaults = bool(options.get("__use_profile_defaults"))
        executable = self._resolve_codex_command()
        if effective_passthrough is not None:
            fallback_flags = self._apply_landlock_flag_fallback(list(effective_passthrough))
            return [executable, *fallback_flags]
        default_flags = self._resolve_profile_flags(action="start", use_profile_defaults=profile_defaults)
        merged_flags = merge_cli_args(default_flags, [])
        merged_flags = self._apply_landlock_flag_fallback(merged_flags)
        return [executable, "exec", *merged_flags, prompt]

    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:
        return self.build_start_with_options(prompt=prompt, options=ctx.options)

    def build_resume_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        session_handle: EngineSessionHandle,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        effective_passthrough = passthrough_args
        if effective_passthrough is None:
            raw = options.get("__passthrough_cli_args")
            if isinstance(raw, list):
                effective_passthrough = [str(item) for item in raw]
        profile_defaults = use_profile_defaults
        if "__use_profile_defaults" in options:
            profile_defaults = bool(options.get("__use_profile_defaults"))

        thread_id = session_handle.handle_value.strip()
        if not thread_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty codex thread id")
        executable = self._resolve_codex_command()
        if effective_passthrough is not None:
            flags = [
                token
                for token in effective_passthrough
                if isinstance(token, str) and token.startswith("-")
            ]
            defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=False)
            merged = merge_cli_args(defaults, flags)
            merged = self._strip_resume_profile_flags(merged)
            merged = self._apply_landlock_flag_fallback(merged)
            return [executable, "exec", "resume", *merged, thread_id, prompt]
        defaults = self._resolve_profile_flags(action="resume", use_profile_defaults=profile_defaults)
        merged = merge_cli_args(defaults, [])
        merged = self._strip_resume_profile_flags(merged)
        merged = self._apply_landlock_flag_fallback(merged)
        return [executable, "exec", "resume", *merged, thread_id, prompt]

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
        )
