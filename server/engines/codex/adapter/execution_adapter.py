from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from server.engines.codex.adapter.sandbox_probe import CodexSandboxProbeResult
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.common.run_folder_validator_common import (
    ProfiledAttemptRunFolderValidator,
)
from server.services.engine_management.agent_cli_manager import AgentCliManager
from .command_builder import CodexCommandBuilder
from .config_composer import CodexConfigComposer
from .stream_parser import CodexStreamParser
from .toml_manager import CodexConfigManager

logger = logging.getLogger(__name__)


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
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(adapter=self, profile=profile)
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

    def get_headless_sandbox_probe(self) -> CodexSandboxProbeResult:
        return self.agent_manager.get_codex_sandbox_probe()

    def _apply_landlock_flag_fallback(self, flags: list[str]) -> list[str]:
        probe = self.get_headless_sandbox_probe()
        if probe.available:
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
        return self.profile.resolve_command_defaults(action=action)

    def cleanup_terminal_run_resources(
        self,
        *,
        skill: Any,
        run_dir: Path,
        options: dict[str, Any],
    ) -> None:
        _ = skill, run_dir
        profile_name = options.get("__codex_mcp_profile_name")
        if not isinstance(profile_name, str) or not profile_name.strip():
            return
        try:
            self.config_manager.remove_profile(profile_name.strip())
        except (OSError, ValueError, TypeError):
            logger.warning(
                "Failed to cleanup Codex per-run MCP profile: %s",
                profile_name,
                exc_info=True,
            )
