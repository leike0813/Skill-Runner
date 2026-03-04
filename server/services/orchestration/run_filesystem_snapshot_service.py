from __future__ import annotations

from pathlib import Path
from typing import Any

from .run_bundle_service import RunBundleService


class RunFilesystemSnapshotService:
    def __init__(self, bundle_service: RunBundleService | None = None):
        self.bundle_service = bundle_service or RunBundleService()

    def capture_filesystem_snapshot(self, run_dir: Path) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        ignored_prefixes = (
            ".audit/",
            ".state/",
            ".codex/",
            ".gemini/",
            ".iflow/",
            ".opencode/",
        )
        ignored_files = {
            "opencode.json",
        }
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            if rel_path.startswith(ignored_prefixes):
                continue
            if rel_path in ignored_files:
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
