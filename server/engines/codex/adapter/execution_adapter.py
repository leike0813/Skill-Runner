from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.common.workspace_provisioner_common import ProfiledWorkspaceProvisioner
from server.services.orchestration.agent_cli_manager import AgentCliManager
from server.engines.codex.adapter.config.toml_manager import CodexConfigManager
from server.services.orchestration.engine_command_profile import engine_command_profile
from .command_builder import CodexCommandBuilder
from .config_composer import CodexConfigComposer
from .stream_parser import CodexStreamParser


class CodexExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, config_manager: Optional[CodexConfigManager] = None, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="Codex")
        profile = load_adapter_profile("codex", Path(__file__).with_name("adapter_profile.json"))
        self.profile = profile
        self.config_manager = config_manager or CodexConfigManager(
            default_config_path=profile.resolve_default_config_path(),
            enforced_config_path=profile.resolve_enforced_config_path(),
            schema_path=profile.resolve_settings_schema_path(),
        )
        self.agent_manager = AgentCliManager()
        self.config_composer = CodexConfigComposer(self)
        self.workspace_provisioner = ProfiledWorkspaceProvisioner(adapter=self, profile=profile)
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=profile)
        self.command_builder = CodexCommandBuilder(self)
        self.stream_parser = CodexStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=profile)

    def build_subprocess_env(self, base_env: dict[str, str]) -> dict[str, str]:
        return self.agent_manager.profile.build_subprocess_env(base_env)

    def _resolve_codex_command(self) -> Path:
        cmd = self.agent_manager.resolve_engine_command("codex")
        if cmd is None:
            raise RuntimeError("Codex CLI not found in managed prefix")
        return cmd

    def _apply_landlock_flag_fallback(self, flags: list[str]) -> list[str]:
        if os.environ.get("LANDLOCK_ENABLED") != "0":
            return flags
        replaced = ["--yolo" if token == "--full-auto" else token for token in flags]
        if "--yolo" in replaced:
            return replaced
        return replaced

    def _strip_resume_profile_flags(self, flags: list[str]) -> list[str]:
        filtered: list[str] = []
        skip_next = False
        for token in flags:
            if skip_next:
                skip_next = False
                continue
            if token in {"-p", "--profile"}:
                skip_next = True
                continue
            if token.startswith("--profile="):
                continue
            filtered.append(token)
        return filtered

    def _resolve_profile_flags(self, *, action: str, use_profile_defaults: bool) -> list[str]:
        if not use_profile_defaults:
            return []
        return engine_command_profile.resolve_args(engine="codex", action=action)
