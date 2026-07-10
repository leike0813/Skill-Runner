from __future__ import annotations

from pathlib import Path
from typing import Any

from server.engines.codebuddy.auth.credential_store import codebuddy_credential_store
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.prompt_builder_common import ProfiledPromptBuilder
from server.runtime.adapter.common.run_folder_validator_common import ProfiledAttemptRunFolderValidator
from server.runtime.adapter.common.session_codec_common import ProfiledSessionCodec
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.engine_management.agent_cli_manager import AgentCliManager

from .command_builder import CodeBuddyCommandBuilder
from .config_composer import CodeBuddyConfigComposer
from .stream_parser import CodeBuddyStreamParser


class CodeBuddyExecutionAdapter(EngineExecutionAdapter):
    _RESERVED_ENV = {"CODEBUDDY_AUTH_TOKEN", "CODEBUDDY_API_KEY", "CODEBUDDY_INTERNET_ENVIRONMENT", "CODEBUDDY_BASE_URL", "CODEBUDDY_CONFIG_DIR"}

    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="CodeBuddy")
        self.profile = load_adapter_profile("codebuddy", Path(__file__).with_name("adapter_profile.json"))
        self.agent_manager = AgentCliManager()
        self.config_composer = CodeBuddyConfigComposer(self)
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(adapter=self, profile=self.profile)
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=self.profile)
        self.command_builder = CodeBuddyCommandBuilder(self)
        self.stream_parser = CodeBuddyStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=self.profile)

    def build_execution_env(self, base_env: dict[str, str], ctx: AdapterExecutionContext, config_path: Path) -> dict[str, str]:
        _ = config_path
        provider = require_provider(ctx.options.get("provider_id"))
        status = codebuddy_credential_store.project_status(provider.provider_id)
        credential = codebuddy_credential_store.get(provider.provider_id)
        if credential is None or status.credential_state != "present":
            raise RuntimeError(f"AUTH_REQUIRED:{provider.provider_id}")
        env = self.agent_manager.profile.build_subprocess_env(base_env)
        for key in self._RESERVED_ENV:
            env.pop(key, None)
        env.update({"CODEBUDDY_AUTH_TOKEN": credential.token, "CODEBUDDY_INTERNET_ENVIRONMENT": provider.runtime_environment, "CODEBUDDY_CONFIG_DIR": str(provider.config_dir(self.agent_manager.profile.agent_home))})
        return env

    def _apply_runtime_env_overlay(self, env: dict[str, str], options: dict[str, Any]) -> dict[str, str]:
        runtime_env = options.get("__runtime_env")
        if isinstance(runtime_env, dict) and self._RESERVED_ENV.intersection(runtime_env):
            raise ValueError("CodeBuddy runtime environment may not override managed credential or routing variables")
        return super()._apply_runtime_env_overlay(env, options)

    def resolve_process_failure_reason(
        self,
        *,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
    ) -> str | None:
        _ = raw_stderr
        parsed = self.stream_parser.parse(raw_stdout)
        turn = parsed.get("turn_result") if isinstance(parsed, dict) else None
        if isinstance(turn, dict) and turn.get("outcome") == "error":
            return str(turn.get("failure_reason") or "CODEBUDDY_TERMINAL_ERROR")
        return "PROCESS_EXIT_NONZERO" if exit_code != 0 else None
