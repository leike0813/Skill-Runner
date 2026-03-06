from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from server.services.engine_management.runtime_profile import get_runtime_profile
from server.engines.codex.adapter.trust_folder_strategy import CodexTrustFolderStrategy
from server.engines.gemini.adapter.trust_folder_strategy import GeminiTrustFolderStrategy


class TrustFolderStrategy(Protocol):
    def register(self, normalized_path: str) -> None:
        ...

    def remove(self, normalized_path: str) -> None:
        ...

    def bootstrap_parent_trust(self, normalized_parent_path: str) -> None:
        ...

    def cleanup_stale(self, active_normalized_paths: set[str]) -> None:
        ...


class _NoopTrustFolderStrategy:
    def register(self, normalized_path: str) -> None:
        _ = normalized_path

    def remove(self, normalized_path: str) -> None:
        _ = normalized_path

    def bootstrap_parent_trust(self, normalized_parent_path: str) -> None:
        _ = normalized_parent_path

    def cleanup_stale(self, active_normalized_paths: set[str]) -> None:
        _ = active_normalized_paths


@dataclass(frozen=True)
class TrustFolderStrategyRegistry:
    _strategies: dict[str, TrustFolderStrategy]
    _noop: TrustFolderStrategy

    def resolve(self, engine: str) -> TrustFolderStrategy:
        normalized = engine.strip().lower()
        return self._strategies.get(normalized, self._noop)

    def iter_registered(self) -> Iterable[tuple[str, TrustFolderStrategy]]:
        return self._strategies.items()


def create_default_trust_registry(
    *,
    codex_config_path: Path | None = None,
    gemini_trusted_path: Path | None = None,
    runs_root: Path,
) -> TrustFolderStrategyRegistry:
    profile = get_runtime_profile()
    codex_path = codex_config_path or (profile.agent_home / ".codex" / "config.toml")
    gemini_path = gemini_trusted_path or (profile.agent_home / ".gemini" / "trustedFolders.json")
    runs_root_resolved = runs_root.resolve()
    return TrustFolderStrategyRegistry(
        _strategies={
            "codex": CodexTrustFolderStrategy(codex_path, runs_root_resolved),
            "gemini": GeminiTrustFolderStrategy(gemini_path, runs_root_resolved),
        },
        _noop=_NoopTrustFolderStrategy(),
    )
