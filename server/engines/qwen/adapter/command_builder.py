from __future__ import annotations

from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import QwenExecutionAdapter


class QwenCommandBuilder:
    """
    Command builder for Qwen Code CLI.

    Builds commands using declarative configuration from adapter_profile.json:
    - Start: qwen --output-format stream-json --approval-mode yolo -p "<prompt>"
    - Resume: qwen --output-format stream-json --approval-mode yolo --resume <id> -p "<prompt>"
    """

    def __init__(self, adapter: "QwenExecutionAdapter") -> None:
        self._adapter = adapter

    def _resolve_qwen_command(self) -> str:
        return str(self._adapter._resolve_qwen_command())

    def build_start_with_options(
        self,
        *,
        prompt: str,
        options: dict[str, object],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        """
        Build start command for Qwen Code.

        Args:
            prompt: The prompt to execute
            options: Runtime options from the request
            passthrough_args: Optional CLI args to pass through
            use_profile_defaults: Whether to use profile default flags

        Returns:
            Command as a list of strings
        """
        executable = self._resolve_qwen_command()

        if passthrough_args is not None:
            return [executable, *passthrough_args]

        default_flags = (
            list(self._adapter.profile.command_defaults.start)
            if use_profile_defaults
            else ["-p"]
        )

        return [executable, *default_flags, prompt]

    def build_start(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
    ) -> list[str]:
        """Build start command from execution context."""
        return self.build_start_with_options(
            prompt=prompt,
            options=ctx.options,
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
        """
        Build resume command for Qwen Code.

        Args:
            prompt: The prompt to continue with
            options: Runtime options from the request
            session_handle: The session handle to resume
            passthrough_args: Optional CLI args to pass through
            use_profile_defaults: Whether to use profile default flags

        Returns:
            Command as a list of strings
        """
        executable = self._resolve_qwen_command()
        session_id = session_handle.handle_value.strip()

        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty qwen session id")

        if passthrough_args is not None:
            flags = [
                token
                for token in passthrough_args
                if isinstance(token, str) and token.startswith("-")
            ]
            if "--resume" not in flags:
                flags.extend(["--resume", session_id])
            if "-p" not in flags and "--prompt" not in flags:
                flags.extend(["-p", prompt])
            return [executable, *flags]

        default_flags = (
            list(self._adapter.profile.command_defaults.resume)
            if use_profile_defaults
            else ["--resume"]
        )

        return [executable, *default_flags, session_id, "-p", prompt]

    def build_resume(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
        session_handle: EngineSessionHandle,
    ) -> list[str]:
        """Build resume command from execution context."""
        return self.build_resume_with_options(
            prompt=prompt,
            options=ctx.options,
            session_handle=session_handle,
        )
