from __future__ import annotations

from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.engine_command_profile import merge_cli_args

if TYPE_CHECKING:
    from .execution_adapter import OpencodeExecutionAdapter


class OpencodeCommandBuilder:
    def __init__(self, adapter: "OpencodeExecutionAdapter") -> None:
        self._adapter = adapter

    def _model_args(self, options: dict[str, object]) -> list[str]:
        model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            return ["--model", model_obj.strip()]
        return []

    def _extract_passthrough_options(
        self,
        passthrough_args: list[str],
        *,
        blocked_option_keys: set[str] | None = None,
    ) -> list[str]:
        blocked = blocked_option_keys or set()
        normalized_blocked = {key.strip() for key in blocked if key.strip()}
        parsed: list[str] = []
        idx = 0
        while idx < len(passthrough_args):
            token = passthrough_args[idx]
            if not isinstance(token, str):
                idx += 1
                continue
            current = token.strip()
            if not current.startswith("-"):
                idx += 1
                continue
            key = current.split("=", 1)[0] if "=" in current else current
            if key in normalized_blocked:
                if "=" not in current and idx + 1 < len(passthrough_args):
                    next_token = passthrough_args[idx + 1]
                    if isinstance(next_token, str) and not next_token.strip().startswith("-"):
                        idx += 2
                        continue
                idx += 1
                continue
            parsed.append(current)
            if "=" not in current and idx + 1 < len(passthrough_args):
                next_token = passthrough_args[idx + 1]
                if isinstance(next_token, str):
                    next_clean = next_token.strip()
                    if next_clean and not next_clean.startswith("-"):
                        parsed.append(next_clean)
                        idx += 2
                        continue
            idx += 1
        return parsed

    def _build_run_command_with_defaults(
        self,
        *,
        prompt: str,
        defaults: list[str],
        explicit_flags: list[str],
        session_id: str | None = None,
        options: dict[str, object],
    ) -> list[str]:
        merged_flags = merge_cli_args(defaults, explicit_flags)
        command: list[str] = [str(self._adapter._resolve_opencode_command()), "run"]  # noqa: SLF001
        if session_id is not None:
            command.append(f"--session={session_id}")
        command.extend(merged_flags)
        command.extend(self._model_args(options))
        command.append(prompt)
        return command

    def build_start_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        executable = str(self._adapter._resolve_opencode_command())  # noqa: SLF001
        if passthrough_args is not None:
            return [executable, *passthrough_args]
        defaults = self._adapter._resolve_profile_flags(  # noqa: SLF001
            action="start",
            use_profile_defaults=use_profile_defaults,
        )
        return self._build_run_command_with_defaults(
            prompt=prompt,
            defaults=defaults,
            explicit_flags=[],
            options=options,
        )

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
            raise RuntimeError("SESSION_RESUME_FAILED: empty opencode session id")
        if passthrough_args is not None:
            flags = self._extract_passthrough_options(
                [str(token) for token in passthrough_args],
                blocked_option_keys={"--session"},
            )
            return self._build_run_command_with_defaults(
                prompt=prompt,
                defaults=[],
                explicit_flags=flags,
                session_id=session_id,
                options=options,
            )
        defaults = self._adapter._resolve_profile_flags(  # noqa: SLF001
            action="resume",
            use_profile_defaults=use_profile_defaults,
        )
        return self._build_run_command_with_defaults(
            prompt=prompt,
            defaults=defaults,
            explicit_flags=[],
            session_id=session_id,
            options=options,
        )

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
