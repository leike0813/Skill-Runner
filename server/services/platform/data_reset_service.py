from __future__ import annotations

import threading
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ...config import config
from ..engine_management.engine_model_catalog_lifecycle import (
    engine_model_catalog_lifecycle,
)


DATA_RESET_CONFIRMATION_TEXT = "RESET SKILL RUNNER DATA"


@dataclass(frozen=True)
class DataResetOptions:
    include_logs: bool = False
    include_engine_catalog: bool = False
    include_engine_auth_sessions: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class ResetTargets:
    data_dir: Path
    db_files: tuple[Path, ...]
    data_dirs: tuple[Path, ...]
    optional_paths: tuple[Path, ...]
    recreate_dirs: tuple[Path, ...]

    def all_paths(self) -> tuple[Path, ...]:
        return self.db_files + self.data_dirs + self.optional_paths


@dataclass(frozen=True)
class ResetPathResult:
    path: Path
    status: str


@dataclass(frozen=True)
class DataResetResult:
    dry_run: bool
    targets: ResetTargets
    path_results: tuple[ResetPathResult, ...]
    deleted_count: int
    missing_count: int
    recreated_count: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "data_dir": str(self.targets.data_dir),
            "db_files": [str(path) for path in self.targets.db_files],
            "data_dirs": [str(path) for path in self.targets.data_dirs],
            "optional_paths": [str(path) for path in self.targets.optional_paths],
            "recreate_dirs": [str(path) for path in self.targets.recreate_dirs],
            "targets": [str(path) for path in self.targets.all_paths()],
            "deleted_count": self.deleted_count,
            "missing_count": self.missing_count,
            "recreated_count": self.recreated_count,
            "path_results": [
                {
                    "path": str(item.path),
                    "status": item.status,
                }
                for item in self.path_results
            ],
        }


class DataResetBusyError(RuntimeError):
    """Raised when a destructive reset is already running in-process."""


class DataResetService:
    def __init__(
        self,
        cfg: Any = config,
        *,
        model_catalog_lifecycle: Any = engine_model_catalog_lifecycle,
    ) -> None:
        self._cfg = cfg
        self._model_catalog_lifecycle = model_catalog_lifecycle
        self._execution_lock = threading.Lock()

    @staticmethod
    def _ordered_unique(paths: Iterable[Path]) -> tuple[Path, ...]:
        ordered: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            ordered.append(resolved)
        return tuple(ordered)

    def build_targets(self, options: DataResetOptions) -> ResetTargets:
        data_dir = Path(self._cfg.SYSTEM.DATA_DIR).resolve()
        include_engine_auth_sessions = bool(options.include_engine_auth_sessions) and bool(
            getattr(self._cfg.SYSTEM, "ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED", False)
        )
        db_files = self._ordered_unique(
            [
                Path(self._cfg.SYSTEM.RUNS_DB),
            ]
        )
        data_dirs = self._ordered_unique(
            [
                Path(self._cfg.SYSTEM.RUNS_DIR),
                Path(self._cfg.SYSTEM.SKILL_INSTALLS_DIR),
            ]
        )

        optional_paths: list[Path] = []
        if options.include_logs:
            optional_paths.append(Path(self._cfg.SYSTEM.LOGGING.DIR))
        if options.include_engine_catalog:
            optional_paths.extend(Path(path) for path in self._model_catalog_lifecycle.cache_paths())
        if include_engine_auth_sessions:
            optional_paths.append(data_dir / "engine_auth_sessions")
        optional_paths.append(data_dir / "ui_shell_sessions")
        optional_paths.append(Path(self._cfg.SYSTEM.TMP_UPLOADS_DIR))
        # Legacy persistence artifacts cleanup (best-effort).
        optional_paths.append(data_dir / "skill_installs.db")
        optional_paths.append(data_dir / "temp_skill_runs.db")
        optional_paths.append(data_dir / "temp_skill_runs")
        optional_paths.append(data_dir / "runtime_process_leases")

        recreate_dirs = self._ordered_unique(
            [
                data_dir,
                Path(self._cfg.SYSTEM.RUNS_DIR),
                Path(self._cfg.SYSTEM.SKILL_INSTALLS_DIR),
                Path(self._cfg.SYSTEM.LOGGING.DIR),
                Path(self._cfg.SYSTEM.TMP_UPLOADS_DIR),
            ]
        )

        return ResetTargets(
            data_dir=data_dir,
            db_files=db_files,
            data_dirs=data_dirs,
            optional_paths=self._ordered_unique(optional_paths),
            recreate_dirs=recreate_dirs,
        )

    @staticmethod
    def _remove_path(path: Path) -> bool:
        if not path.exists():
            return False
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            return True
        path.unlink()
        return True

    def execute_reset(self, options: DataResetOptions) -> DataResetResult:
        targets = self.build_targets(options)
        if options.dry_run:
            preview_results: list[ResetPathResult] = []
            deleted_count = 0
            missing_count = 0
            for path in targets.all_paths():
                exists = path.exists()
                status = "would_delete" if exists else "missing"
                preview_results.append(ResetPathResult(path=path, status=status))
                if exists:
                    deleted_count += 1
                else:
                    missing_count += 1
            return DataResetResult(
                dry_run=True,
                targets=targets,
                path_results=tuple(preview_results),
                deleted_count=deleted_count,
                missing_count=missing_count,
                recreated_count=len(targets.recreate_dirs),
            )

        if not self._execution_lock.acquire(blocking=False):
            raise DataResetBusyError("Data reset is already running")

        try:
            path_results: list[ResetPathResult] = []
            deleted_count = 0
            missing_count = 0
            for path in targets.all_paths():
                deleted = self._remove_path(path)
                status = "deleted" if deleted else "missing"
                path_results.append(ResetPathResult(path=path, status=status))
                if deleted:
                    deleted_count += 1
                else:
                    missing_count += 1

            for path in targets.recreate_dirs:
                path.mkdir(parents=True, exist_ok=True)

            return DataResetResult(
                dry_run=False,
                targets=targets,
                path_results=tuple(path_results),
                deleted_count=deleted_count,
                missing_count=missing_count,
                recreated_count=len(targets.recreate_dirs),
            )
        finally:
            self._execution_lock.release()


data_reset_service = DataResetService()
