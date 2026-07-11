from __future__ import annotations

from pathlib import Path
from typing import Any

from server.engines.codebuddy.auth.credential_store import codebuddy_credential_store
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.engines.codebuddy.managed_environment import build_codebuddy_managed_env
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
from server.engines.codebuddy.secret_redaction import CodeBuddySecretRedactor


class CodeBuddyExecutionAdapter(EngineExecutionAdapter):
    def __init__(self, **kwargs: Any) -> None:
        _ = kwargs
        super().__init__(process_prefix="CodeBuddy")
        self.profile = load_adapter_profile("codebuddy", Path(__file__).with_name("adapter_profile.json"))
        self._reserved_env = frozenset(self.profile.launch.managed_env_keys)
        self.agent_manager = AgentCliManager()
        self.config_composer = CodeBuddyConfigComposer(self)
        self.run_folder_validator = ProfiledAttemptRunFolderValidator(adapter=self, profile=self.profile)
        self.prompt_builder = ProfiledPromptBuilder(adapter=self, profile=self.profile)
        self.command_builder = CodeBuddyCommandBuilder(self)
        self.stream_parser = CodeBuddyStreamParser(self)
        self.session_codec = ProfiledSessionCodec(profile=self.profile)

    def build_execution_env(self, base_env: dict[str, str], ctx: AdapterExecutionContext, config_path: Path) -> dict[str, str]:
        _ = config_path
        return build_codebuddy_managed_env(
            base_env=base_env,
            provider_id=ctx.options.get("provider_id"),
            managed_env_keys=self._reserved_env,
            agent_manager=self.agent_manager,
        )

    def _apply_runtime_env_overlay(self, env: dict[str, str], options: dict[str, Any]) -> dict[str, str]:
        runtime_env = options.get("__runtime_env")
        if isinstance(runtime_env, dict) and self._reserved_env.intersection(runtime_env):
            raise ValueError("CodeBuddy runtime environment may not override managed credential or routing variables")
        return super()._apply_runtime_env_overlay(env, options)

    def create_output_redactor(
        self,
        *,
        options: dict[str, Any],
        stream_name: str,
    ) -> CodeBuddySecretRedactor:
        _ = stream_name
        provider = require_provider(options.get("provider_id"))
        credential = codebuddy_credential_store.get(provider.provider_id)
        secrets = () if credential is None else (credential.token, credential.user_id)
        return CodeBuddySecretRedactor(secrets=secrets)

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
