from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List

from ....config import config


@dataclass(frozen=True)
class OpencodeAuthProvider:
    provider_id: str
    display_name: str
    auth_mode: str
    menu_label: str


class OpencodeAuthProviderRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: Dict[str, OpencodeAuthProvider] = {}
        self._ordered_ids: List[str] = []
        self._loaded = False

    def _config_path(self) -> Path:
        return (
            Path(config.SYSTEM.ROOT)
            / "server"
            / "assets"
            / "configs"
            / "opencode"
            / "auth_providers.json"
        )

    def _load_locked(self) -> None:
        if self._loaded:
            return
        path = self._config_path()
        payload = json.loads(path.read_text(encoding="utf-8"))
        providers = payload.get("providers", [])
        mapped: Dict[str, OpencodeAuthProvider] = {}
        ordered: List[str] = []
        for row in providers:
            provider = OpencodeAuthProvider(
                provider_id=str(row["provider_id"]).strip(),
                display_name=str(row["display_name"]).strip(),
                auth_mode=str(row["auth_mode"]).strip().lower(),
                menu_label=str(row["menu_label"]).strip(),
            )
            if provider.auth_mode not in {"oauth", "api_key"}:
                raise ValueError(f"Unsupported auth mode for provider '{provider.provider_id}'")
            mapped[provider.provider_id] = provider
            ordered.append(provider.provider_id)
        self._providers = mapped
        self._ordered_ids = ordered
        self._loaded = True

    def list(self) -> List[OpencodeAuthProvider]:
        with self._lock:
            self._load_locked()
            return [self._providers[key] for key in self._ordered_ids]

    def get(self, provider_id: str) -> OpencodeAuthProvider:
        key = provider_id.strip().lower()
        with self._lock:
            self._load_locked()
            provider = self._providers.get(key)
            if provider is None:
                raise ValueError(f"Unsupported opencode provider: {provider_id}")
            return provider


opencode_auth_provider_registry = OpencodeAuthProviderRegistry()
