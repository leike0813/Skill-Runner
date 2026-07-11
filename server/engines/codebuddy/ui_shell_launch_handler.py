from __future__ import annotations

from pathlib import Path

from server.engines.codebuddy.auth.credential_store import codebuddy_credential_store
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.engines.codebuddy.managed_environment import build_codebuddy_managed_env
from server.engines.codebuddy.storage_layout import atomic_write_json
from server.runtime.adapter.common.profile_loader import AdapterProfile
from server.runtime.adapter.types import AdapterAuthenticationRequired
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.ui.ui_shell_launch_handler import (
    UiShellLaunchPlan,
    UiShellLaunchValidationError,
)


class CodeBuddyUiShellLaunchHandler:
    def __init__(self, profile: AdapterProfile) -> None:
        self._managed_env_keys = frozenset(profile.launch.managed_env_keys)

    def validate(self, provider_id: str | None) -> str:
        try:
            provider = require_provider(provider_id)
        except ValueError as exc:
            raise UiShellLaunchValidationError(str(exc)) from exc
        state = codebuddy_credential_store.project_status(provider.provider_id).credential_state
        if state != "present":
            raise UiShellLaunchValidationError(
                f"CodeBuddy provider credential is {state}: {provider.provider_id}"
            )
        return provider.provider_id

    def prepare(
        self,
        *,
        session_dir: Path,
        base_env: dict[str, str],
        launch_args: tuple[str, ...],
        provider_id: str | None,
        agent_manager: AgentCliManager,
    ) -> UiShellLaunchPlan:
        canonical_provider = self.validate(provider_id)
        try:
            env = build_codebuddy_managed_env(
                base_env=base_env,
                provider_id=canonical_provider,
                managed_env_keys=self._managed_env_keys,
                agent_manager=agent_manager,
            )
        except AdapterAuthenticationRequired as exc:
            reason = exc.signal.get("reason_code") or "AUTH_REQUIRED"
            raise UiShellLaunchValidationError(str(reason)) from exc

        mcp_path = session_dir / ".codebuddy" / "mcp.json"
        atomic_write_json(mcp_path, {"mcpServers": {}})
        args = (*launch_args, "--mcp-config", str(mcp_path), "--strict-mcp-config")
        return UiShellLaunchPlan(
            args=args,
            env=env,
            provider_id=canonical_provider,
        )
