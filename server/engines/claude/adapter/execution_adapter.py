from __future__ import annotations

from pathlib import Path
from typing import Any

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.run_folder_validator_common import ProfiledAttemptRunFolderValidator
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.services.engine_management.agent_cli_manager import AgentCliManager

from .command_builder import ClaudeCommandBuilder
from .config_composer import ClaudeConfigComposer
from .mcp_materializer import cleanup_claude_run_local_mcp
from .prompt_builder import ClaudePromptBuilder
from .stream_parser import ClaudeStreamParser


class ClaudeExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="Claude")
        profile = load_adapter_profile("claude", Path(__file__).with_name("adapter_profile.json"))
        self.profile = profile
        self.agent_manager = AgentCliManager()
        self.config_composer = ClaudeConfigComposer(self)
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(adapter=self, profile=profile)
        self.prompt_builder = ClaudePromptBuilder(adapter=self, profile=profile)
        self.command_builder = ClaudeCommandBuilder(self)
        self.stream_parser = ClaudeStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        env = self.agent_manager.profile.build_subprocess_env(base_env)
        env["CLAUDE_CONFIG_DIR"] = str(self.agent_manager.profile.agent_home / ".claude")
        return env

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return self.profile.resolve_command_defaults(action=action)

    def cleanup_terminal_run_resources(
        self,
        *,
        skill: Any,
        run_dir: Path,
        options: dict[str, Any],
    ) -> None:
        _ = skill, options
        cleanup_claude_run_local_mcp(
            agent_home=self.agent_manager.profile.agent_home,
            run_dir=run_dir,
        )
