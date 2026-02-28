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
from .command_builder import IFlowCommandBuilder
from .config_composer import IFlowConfigComposer
from .stream_parser import IFlowStreamParser


class IFlowExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="IFlow")
        profile = load_adapter_profile("iflow", Path(__file__).with_name("adapter_profile.json"))
        self.profile = profile
        self.agent_manager = AgentCliManager()
        self.config_composer = IFlowConfigComposer(self)
        self.workspace_provisioner = ProfiledWorkspaceProvisioner(adapter=self, profile=profile)
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=profile)
        self.command_builder = IFlowCommandBuilder(self)
        self.stream_parser = IFlowStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return self.agent_manager.profile.build_subprocess_env(base_env)

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="iflow", action=action)
