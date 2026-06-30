from __future__ import annotations

from pathlib import Path
from typing import Any

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.run_folder_validator_common import (
    ProfiledAttemptRunFolderValidator,
)
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.engine_management.agent_cli_manager import AgentCliManager

from .command_builder import KiloCommandBuilder
from .config_composer import KiloConfigComposer
from .stream_parser import KiloStreamParser


class KiloExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="Kilo")

        profile = load_adapter_profile(
            "kilo", Path(__file__).with_name("adapter_profile.json")
        )
        self.profile = profile

        self.agent_manager = AgentCliManager()
        self.config_composer = KiloConfigComposer(self)
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(
            adapter=self, profile=profile
        )
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=profile)
        self.command_builder = KiloCommandBuilder(self)
        self.stream_parser = KiloStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return self.agent_manager.profile.build_subprocess_env(base_env)

    def build_execution_env(
        self,
        base_env: dict[str, str],
        ctx: AdapterExecutionContext,
        config_path: Path,
    ) -> dict[str, str]:
        _ = ctx
        env = self.build_subprocess_env(base_env)
        config_env_var = self.profile.launch.config_env_var
        if isinstance(config_env_var, str) and config_env_var:
            env[config_env_var] = str(config_path)
        return env

    def _resolve_kilo_command(self) -> Path:
        cmd = self.agent_manager.resolve_engine_command("kilo")
        if cmd is None:
            raise RuntimeError("Kilo Code CLI not found in managed prefix")
        return cmd
