from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Dict, List

from server.engines.opencode.auth.provider_registry import (
    opencode_auth_provider_registry,
)


@dataclass(frozen=True)
class KiloAuthProvider:
    provider_id: str
    display_name: str
    auth_mode: str
    menu_label: str
    supports_import: bool


class KiloAuthProviderRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: Dict[str, KiloAuthProvider] = {}
        self._ordered_ids: List[str] = []
        self._loaded = False

    def _load_locked(self) -> None:
        if self._loaded:
            return
        mapped: Dict[str, KiloAuthProvider] = {
            "kilo": KiloAuthProvider(
                provider_id="kilo",
                display_name="Kilo Gateway",
                auth_mode="oauth",
                menu_label="Kilo Gateway",
                supports_import=False,
            )
        }
        ordered: List[str] = ["kilo"]
        for provider in opencode_auth_provider_registry.list():
            provider_id = provider.provider_id.strip().lower()
            if provider_id in mapped:
                continue
            mapped[provider_id] = KiloAuthProvider(
                provider_id=provider_id,
                display_name=provider.display_name,
                auth_mode=provider.auth_mode,
                menu_label=provider.menu_label,
                supports_import=provider.supports_import,
            )
            ordered.append(provider_id)
        self._providers = mapped
        self._ordered_ids = ordered
        self._loaded = True

    def list(self) -> List[KiloAuthProvider]:
        with self._lock:
            self._load_locked()
            return [self._providers[key] for key in self._ordered_ids]

    def get(self, provider_id: str) -> KiloAuthProvider:
        key = provider_id.strip().lower()
        with self._lock:
            self._load_locked()
            provider = self._providers.get(key)
            if provider is None:
                raise ValueError(f"Unsupported kilo provider: {provider_id}")
            return provider


kilo_auth_provider_registry = KiloAuthProviderRegistry()
