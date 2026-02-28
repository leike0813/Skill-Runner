from pathlib import Path
from typing import Iterable

from server.config import config
from server.engines.common.trust_registry import create_default_trust_registry
from server.services.orchestration.runtime_profile import get_runtime_profile

class RunFolderTrustManager:
    """Dispatch run-folder trust operations to engine-registered strategies."""

    def __init__(
        self,
        codex_config_path: Path | None = None,
        gemini_trusted_path: Path | None = None,
        runs_root: Path | None = None,
    ) -> None:
        profile = get_runtime_profile()
        self.codex_config_path = codex_config_path or (profile.agent_home / ".codex" / "config.toml")
        self.gemini_trusted_path = gemini_trusted_path or (
            profile.agent_home / ".gemini" / "trustedFolders.json"
        )
        self.runs_root = (runs_root or Path(config.SYSTEM.RUNS_DIR)).resolve()
        self._registry = create_default_trust_registry(
            codex_config_path=self.codex_config_path,
            gemini_trusted_path=self.gemini_trusted_path,
            runs_root=self.runs_root,
        )

    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        normalized = self._normalize_path(run_dir)
        self._registry.resolve(engine).register(normalized)

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        normalized = self._normalize_path(run_dir)
        self._registry.resolve(engine).remove(normalized)

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        normalized = self._normalize_path(runs_parent)
        for _engine, strategy in self._registry.iter_registered():
            strategy.bootstrap_parent_trust(normalized)

    def cleanup_stale_entries(self, active_run_dirs: Iterable[Path]) -> None:
        active = {self._normalize_path(path) for path in active_run_dirs}
        for _engine, strategy in self._registry.iter_registered():
            strategy.cleanup_stale(active)

    def _normalize_path(self, path: Path) -> str:
        return str(path.resolve())

run_folder_trust_manager = RunFolderTrustManager()
