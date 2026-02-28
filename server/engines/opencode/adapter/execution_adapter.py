from __future__ import annotations

from pathlib import Path
from typing import Any

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.common.workspace_provisioner_common import ProfiledWorkspaceProvisioner
from server.services.agent_cli_manager import AgentCliManager
from server.services.engine_command_profile import engine_command_profile
from .command_builder import OpencodeCommandBuilder
from .config_composer import OpencodeConfigComposer
from .stream_parser import OpencodeStreamParser


class OpencodeExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="Opencode")
        profile = load_adapter_profile("opencode", Path(__file__).with_name("adapter_profile.json"))
        self.profile = profile
        self.agent_manager = AgentCliManager()
        self.config_composer = OpencodeConfigComposer(self)
        self.workspace_provisioner = ProfiledWorkspaceProvisioner(adapter=self, profile=profile)
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=profile)
        self.command_builder = OpencodeCommandBuilder(self)
        self.stream_parser = OpencodeStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        env = self.agent_manager.profile.build_subprocess_env(base_env)
        env.setdefault("OPENCODE_CONFIG", "opencode.json")
        return env

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="opencode", action=action)

    def _resolve_opencode_command(self) -> Path:
        command = self.agent_manager.resolve_engine_command("opencode")
        if command is None:
            raise RuntimeError("OpenCode CLI not found in managed prefix")
        return command
