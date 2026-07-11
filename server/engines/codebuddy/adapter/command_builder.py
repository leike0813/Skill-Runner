from __future__ import annotations

from typing import TYPE_CHECKING

from server.models import EngineSessionHandle
from server.runtime.adapter.common.structured_output_pipeline import structured_output_pipeline
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import CodeBuddyExecutionAdapter


class CodeBuddyCommandBuilder:
    def __init__(self, adapter: "CodeBuddyExecutionAdapter") -> None:
        self._adapter = adapter

    def _command(self) -> str:
        command = self._adapter.agent_manager.resolve_engine_command("codebuddy")
        if command is None:
            raise RuntimeError("CodeBuddy CLI not found in managed prefix")
        return str(command)

    def _managed_flags(self, ctx: AdapterExecutionContext) -> list[str]:
        settings = ctx.run_dir / ".codebuddy" / "settings.json"
        mcp = ctx.run_dir / ".codebuddy" / "mcp.json"
        flags = ["--settings", str(settings), "--setting-sources", "project", "--mcp-config", str(mcp), "--strict-mcp-config"]
        flags.extend(structured_output_pipeline.build_cli_schema_args(engine_name="codebuddy", run_dir=ctx.run_dir, options=ctx.options, profile=self._adapter.profile))
        model = ctx.options.get("runtime_model")
        if isinstance(model, str) and model.strip():
            flags.extend(["--model", model.strip()])
        return flags

    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:
        return [self._command(), *self._adapter.profile.resolve_command_defaults(action="start"), *self._managed_flags(ctx), prompt]

    def build_resume(self, ctx: AdapterExecutionContext, prompt: str, session_handle: EngineSessionHandle) -> list[str]:
        session_id = session_handle.handle_value.strip()
        if not session_id:
            raise RuntimeError("SESSION_RESUME_FAILED: empty codebuddy session_id")
        provider_id = str(ctx.options.get("provider_id") or "").strip().lower()
        if session_handle.provider_id is not None and session_handle.provider_id != provider_id:
            raise RuntimeError("SESSION_RESUME_FAILED: codebuddy provider mismatch")
        return [self._command(), *self._adapter.profile.resolve_command_defaults(action="resume"), "-r", session_id, *self._managed_flags(ctx), prompt]
