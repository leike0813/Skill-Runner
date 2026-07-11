from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from server.engines.codebuddy.auth.credential_store import (
    CodeBuddyCredentialStore,
    codebuddy_credential_store,
)
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.engines.codebuddy.storage_layout import ensure_private_dir, provider_runtime_dir
from server.runtime.adapter.types import AdapterAuthenticationRequired, RuntimeAuthSignal
from server.services.engine_management.agent_cli_manager import AgentCliManager


def build_codebuddy_managed_env(
    *,
    base_env: dict[str, str],
    provider_id: str | None,
    managed_env_keys: Iterable[str],
    agent_manager: AgentCliManager,
    credential_store: CodeBuddyCredentialStore = codebuddy_credential_store,
) -> dict[str, str]:
    """Build the only credential-bearing environment used by CodeBuddy launches."""

    provider = require_provider(provider_id)
    status = credential_store.project_status(provider.provider_id)
    credential = credential_store.get(provider.provider_id)
    if credential is None or status.credential_state == "missing":
        raise _authentication_required(
            provider_id=provider.provider_id,
            reason_code="CODEBUDDY_CREDENTIAL_MISSING",
            subcategory="oauth_reauth",
        )
    if status.credential_state == "expired":
        raise _authentication_required(
            provider_id=provider.provider_id,
            reason_code="CODEBUDDY_CREDENTIAL_EXPIRED",
            subcategory="auth_expired",
        )

    env = agent_manager.profile.build_subprocess_env(base_env)
    for key in managed_env_keys:
        env.pop(key, None)
    config_dir = ensure_private_dir(
        provider_runtime_dir(provider.provider_id, Path(agent_manager.profile.agent_home))
    )
    env.update(
        {
            "CODEBUDDY_AUTH_TOKEN": credential.token,
            "CODEBUDDY_INTERNET_ENVIRONMENT": provider.runtime_environment,
            "CODEBUDDY_CONFIG_DIR": str(config_dir),
        }
    )
    return env


def _authentication_required(
    *,
    provider_id: str,
    reason_code: str,
    subcategory: str,
) -> AdapterAuthenticationRequired:
    signal: RuntimeAuthSignal = {
        "required": True,
        "confidence": "high",
        "subcategory": subcategory,
        "provider_id": provider_id,
        "reason_code": reason_code,
        "matched_pattern_id": reason_code.lower(),
    }
    return AdapterAuthenticationRequired(signal)
