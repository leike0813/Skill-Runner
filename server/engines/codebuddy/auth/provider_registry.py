from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class CodeBuddyProvider:
    provider_id: str
    display_name: str
    sdk_environment: str
    runtime_environment: str
    auth_mode: str = "oauth"
    menu_label: str = ""
    supports_import: bool = False

    def config_dir(self, agent_home: Path) -> Path:
        return agent_home / ".codebuddy-runtime" / self.provider_id


_PROVIDERS: Final[dict[str, CodeBuddyProvider]] = {
    "codebuddy-cn": CodeBuddyProvider(
        provider_id="codebuddy-cn",
        display_name="CodeBuddy 国内版",
        sdk_environment="internal",
        runtime_environment="internal",
        menu_label="CodeBuddy 国内版",
    ),
    "codebuddy-global": CodeBuddyProvider(
        provider_id="codebuddy-global",
        display_name="CodeBuddy 国际版",
        sdk_environment="public",
        runtime_environment="public",
        menu_label="CodeBuddy 国际版",
    ),
}

CODEBUDDY_PROVIDER_IDS: Final[tuple[str, ...]] = tuple(_PROVIDERS)


def get_provider(provider_id: str | None) -> CodeBuddyProvider | None:
    if not isinstance(provider_id, str):
        return None
    return _PROVIDERS.get(provider_id.strip())


def require_provider(provider_id: str | None) -> CodeBuddyProvider:
    provider = get_provider(provider_id)
    if provider is None:
        expected = ", ".join(CODEBUDDY_PROVIDER_IDS)
        raise ValueError(f"CodeBuddy provider_id must be one of: {expected}")
    return provider


def list_providers() -> tuple[CodeBuddyProvider, ...]:
    return tuple(_PROVIDERS.values())


class CodeBuddyProviderRegistry:
    def list(self) -> tuple[CodeBuddyProvider, ...]:
        return list_providers()

    def get(self, provider_id: str) -> CodeBuddyProvider:
        return require_provider(provider_id)


codebuddy_provider_registry = CodeBuddyProviderRegistry()
