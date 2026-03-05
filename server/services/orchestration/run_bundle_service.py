from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from server.services.platform.run_file_filter_service import run_file_filter_service


class RunBundleService:
    def build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
        bundle_dir = run_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_filename = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        bundle_path = bundle_dir / bundle_filename
        manifest_filename = "manifest_debug.json" if debug else "manifest.json"
        manifest_path = bundle_dir / manifest_filename

        entries: list[dict[str, object]] = []
        bundle_candidates = self.bundle_candidates(
            run_dir=run_dir,
            debug=debug,
            bundle_path=bundle_path,
            manifest_path=manifest_path,
        )
        for path in bundle_candidates:
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            entries.append(
                {
                    "path": rel_path,
                    "size": path.stat().st_size,
                    "sha256": self.hash_file(path),
                }
            )

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"files": entries}, f, indent=2)

        if bundle_path.exists():
            bundle_path.unlink()

        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in bundle_candidates:
                if not path.is_file():
                    continue
                rel_path = path.relative_to(run_dir).as_posix()
                zf.write(path, rel_path)
            zf.write(manifest_path, manifest_path.relative_to(run_dir).as_posix())

        return bundle_path.relative_to(run_dir).as_posix()

    def bundle_candidates(
        self,
        run_dir: Path,
        debug: bool,
        bundle_path: Path,
        manifest_path: Path,
    ) -> list[Path]:
        candidates = []
        for path in run_dir.rglob("*"):
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            if debug:
                if run_file_filter_service.include_in_debug_bundle(rel_path):
                    candidates.append(path)
            elif run_file_filter_service.include_in_non_debug_bundle(rel_path):
                candidates.append(path)

        bundle_dir = run_dir / "bundle"
        candidates = [
            path
            for path in candidates
            if path != bundle_path and path != manifest_path and path.parent != bundle_dir
        ]
        return candidates

    def hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
