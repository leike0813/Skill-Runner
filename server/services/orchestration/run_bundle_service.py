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
        if debug:
            candidates = []
            for path in run_dir.rglob("*"):
                if not path.is_file():
                    continue
                rel_path = path.relative_to(run_dir).as_posix()
                if run_file_filter_service.include_in_debug_bundle(rel_path):
                    candidates.append(path)
        else:
            candidates = self._contract_driven_non_debug_candidates(run_dir)

        bundle_dir = run_dir / "bundle"
        candidates = [
            path
            for path in candidates
            if path != bundle_path and path != manifest_path and path.parent != bundle_dir
        ]
        return candidates

    def _contract_driven_non_debug_candidates(self, run_dir: Path) -> list[Path]:
        result_path = run_dir / "result" / "result.json"
        candidates: list[Path] = []
        if result_path.exists():
            candidates.append(result_path)
        if not result_path.exists():
            return candidates

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return candidates
        artifacts_obj = payload.get("artifacts")
        if not isinstance(artifacts_obj, list):
            return candidates
        for rel_path in artifacts_obj:
            if not isinstance(rel_path, str) or not rel_path.strip():
                continue
            path = (run_dir / rel_path.strip()).resolve()
            try:
                path.relative_to(run_dir.resolve())
            except ValueError:
                continue
            if path.exists() and path.is_file():
                candidates.append(path)
        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            rel = path.relative_to(run_dir).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            unique.append(path)
        return unique

    def hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
