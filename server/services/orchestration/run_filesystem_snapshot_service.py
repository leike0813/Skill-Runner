from __future__ import annotations

from pathlib import Path
from typing import Any

from server.config import config
from server.config_registry import keys
from server.runtime.adapter.common.profile_loader import load_adapter_profile

from .run_bundle_service import RunBundleService


class RunFilesystemSnapshotService:
    def __init__(self, bundle_service: RunBundleService | None = None):
        self.bundle_service = bundle_service or RunBundleService()
        self._ignored_prefixes = self._build_ignored_prefixes()
        self._ignored_files = self._build_ignored_files()

    def _readonly_engine_keys(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*keys.ENGINE_KEYS, *keys.LEGACY_READONLY_ENGINE_KEYS)))

    def _build_ignored_prefixes(self) -> tuple[str, ...]:
        ignored = {".audit/", ".state/", ".git/"}
        for engine in self._readonly_engine_keys():
            profile_path = (
                Path(config.SYSTEM.ROOT) / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
            )
            try:
                workspace_subdir = load_adapter_profile(engine, profile_path).attempt_workspace.workspace_subdir
            except RuntimeError:
                workspace_subdir = f".{engine}"
            normalized = workspace_subdir.strip().strip("/")
            if normalized:
                ignored.add(f"{normalized}/")
        return tuple(sorted(ignored))

    def _build_ignored_files(self) -> set[str]:
        ignored_files: set[str] = set()
        for engine in self._readonly_engine_keys():
            ignored_files.add(f"{engine}.json")
        return ignored_files

    def capture_filesystem_snapshot(self, run_dir: Path) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            if rel_path.startswith(self._ignored_prefixes):
                continue
            if rel_path in self._ignored_files:
                continue
            snapshot[rel_path] = {
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "sha256": self.bundle_service.hash_file(path),
            }
        return snapshot

    def diff_filesystem_snapshot(
        self,
        before_snapshot: dict[str, dict[str, Any]],
        after_snapshot: dict[str, dict[str, Any]],
    ) -> dict[str, list[str]]:
        before_keys = set(before_snapshot.keys())
        after_keys = set(after_snapshot.keys())
        created = sorted(after_keys - before_keys)
        deleted = sorted(before_keys - after_keys)
        modified = sorted(
            path
            for path in (before_keys & after_keys)
            if before_snapshot[path].get("sha256") != after_snapshot[path].get("sha256")
        )
        return {"created": created, "modified": modified, "deleted": deleted}
