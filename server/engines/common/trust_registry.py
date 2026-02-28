from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

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
    codex_config_path: Path,
    gemini_trusted_path: Path,
    runs_root: Path,
) -> TrustFolderStrategyRegistry:
    runs_root_resolved = runs_root.resolve()
    return TrustFolderStrategyRegistry(
        _strategies={
            "codex": CodexTrustFolderStrategy(codex_config_path, runs_root_resolved),
            "gemini": GeminiTrustFolderStrategy(gemini_trusted_path, runs_root_resolved),
        },
        _noop=_NoopTrustFolderStrategy(),
    )
