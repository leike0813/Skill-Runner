from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.common.run_folder_validator_common import (
    ProfiledAttemptRunFolderValidator,
)
from server.services.engine_management.agent_cli_manager import AgentCliManager

from .command_builder import QwenCommandBuilder
from .config_composer import QwenConfigComposer
from .stream_parser import QwenStreamParser


class QwenExecutionAdapter(EngineExecutionAdapter):
    """
    Execution adapter for Qwen Code engine.

    Supports:
    - Qwen OAuth authentication
    - Alibaba Cloud Coding Plan authentication
    - Stream-JSON output format
    - Session resume via --resume flag
    """

    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="Qwen")

        profile = load_adapter_profile(
            "qwen", Path(__file__).with_name("adapter_profile.json")
        )
        self.profile = profile

        self.agent_manager = AgentCliManager()
        self.config_composer = QwenConfigComposer(self)
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(
            adapter=self, profile=profile
        )
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=profile)
        self.command_builder = QwenCommandBuilder(self)
        self.stream_parser = QwenStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return self.agent_manager.profile.build_subprocess_env(base_env)

    def _resolve_qwen_command(self) -> Path:
        """Resolve the qwen CLI command path."""
        cmd = self.agent_manager.resolve_engine_command("qwen")
        if cmd is None:
            raise RuntimeError("Qwen Code CLI not found in managed prefix")
        return cmd
