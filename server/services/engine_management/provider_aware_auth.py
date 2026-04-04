from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, cast

from server.engines.opencode.auth.provider_registry import (
    opencode_auth_provider_registry,
)
from server.engines.qwen.auth.provider_registry_impl import qwen_auth_provider_registry


@dataclass(frozen=True)
class EngineAuthProviderMetadata:
    engine: str
    provider_id: str
    display_name: str
    auth_mode: str
    menu_label: str
    supports_import: bool


class _ProviderRecord(Protocol):
    provider_id: str
    display_name: str
    auth_mode: str
    menu_label: str
    supports_import: bool


class _ProviderRegistry(Protocol):
    def list(self) -> Sequence[_ProviderRecord]:
        ...

    def get(self, provider_id: str) -> _ProviderRecord:
        ...


_PROVIDER_REGISTRIES: dict[str, _ProviderRegistry] = {
    "opencode": cast(_ProviderRegistry, opencode_auth_provider_registry),
    "qwen": cast(_ProviderRegistry, qwen_auth_provider_registry),
}


def provider_aware_engines() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDER_REGISTRIES.keys()))


def is_provider_aware_engine(engine: str) -> bool:
    return engine.strip().lower() in _PROVIDER_REGISTRIES


def list_engine_auth_providers(engine: str) -> tuple[EngineAuthProviderMetadata, ...]:
    normalized = engine.strip().lower()
    registry = _PROVIDER_REGISTRIES.get(normalized)
    if registry is None:
        return ()
    return tuple(
        EngineAuthProviderMetadata(
            engine=normalized,
            provider_id=str(provider.provider_id).strip().lower(),
            display_name=str(provider.display_name).strip(),
            auth_mode=str(provider.auth_mode).strip().lower(),
            menu_label=str(provider.menu_label).strip(),
            supports_import=bool(getattr(provider, "supports_import", False)),
        )
        for provider in registry.list()
    )


def get_engine_auth_provider(
    engine: str,
    provider_id: str | None,
) -> EngineAuthProviderMetadata:
    normalized_engine = engine.strip().lower()
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise ValueError(f"provider_id is required for {normalized_engine} auth")
    registry = _PROVIDER_REGISTRIES.get(normalized_engine)
    if registry is None:
        raise ValueError(f"Engine does not support provider-aware auth: {engine}")
    provider = registry.get(provider_id)
    return EngineAuthProviderMetadata(
        engine=normalized_engine,
        provider_id=str(provider.provider_id).strip().lower(),
        display_name=str(provider.display_name).strip(),
        auth_mode=str(provider.auth_mode).strip().lower(),
        menu_label=str(provider.menu_label).strip(),
        supports_import=bool(getattr(provider, "supports_import", False)),
    )
