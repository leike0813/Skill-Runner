from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

from server.runtime.bundle_errors import (
    BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID,
    BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING,
    BundleAssemblyError,
)
from server.runtime.workspace_layout import RunWorkspaceLayout
from server.services.platform.run_file_filter_service import run_file_filter_service

SKILL_RUN_FEEDBACK_FILENAME = "_skill_run_feedback.md"


class RunBundleService:
    def build_run_bundle(
        self,
        run_dir: Path,
        debug: bool = False,
        *,
        layout: RunWorkspaceLayout,
    ) -> str:
        run_dir = layout.workspace_dir
        bundle_dir = layout.bundle_dir
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = layout.bundle_path(debug=debug)
        manifest_path = layout.bundle_manifest_path(debug=debug)

        entries: list[dict[str, object]] = []
        bundle_candidates = self.bundle_candidates(
            run_dir=run_dir,
            debug=debug,
            bundle_path=bundle_path,
            manifest_path=manifest_path,
            layout=layout,
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
        layout: RunWorkspaceLayout,
    ) -> list[Path]:
        if debug:
            candidates = self._contract_driven_debug_candidates(run_dir, layout)
        else:
            candidates = self._contract_driven_non_debug_candidates(
                run_dir,
                result_path=layout.result_path,
            )

        bundle_root = run_dir / "bundle"
        candidates = [
            path
            for path in candidates
            if path != bundle_path
            and path != manifest_path
            and not self._is_relative_to(path, bundle_root)
        ]
        return candidates

    def _contract_driven_non_debug_candidates(
        self,
        run_dir: Path,
        *,
        result_path: Path | None = None,
    ) -> list[Path]:
        candidates: list[Path] = []
        result_candidates = [result_path] if result_path is not None and result_path.exists() else []
        candidates.extend(result_candidates)
        candidates.extend(self._feedback_sidecar_candidates(result_candidates))
        if not result_candidates:
            return candidates

        candidates.extend(
            self._artifact_candidates_from_result(run_dir, result_candidates[-1])
        )
        return self._dedupe_candidates(run_dir, candidates)

    def _contract_driven_debug_candidates(
        self,
        run_dir: Path,
        layout: RunWorkspaceLayout,
    ) -> list[Path]:
        candidates: list[Path] = []
        for root in (
            layout.result_path.parent,
            layout.audit_dir,
        ):
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel_path = path.relative_to(run_dir).as_posix()
                if run_file_filter_service.include_in_debug_bundle(rel_path):
                    candidates.append(path)

        if layout.result_path.exists():
            candidates.extend(
                self._artifact_candidates_from_result(run_dir, layout.result_path)
            )
        return self._dedupe_candidates(run_dir, candidates)

    def _feedback_sidecar_candidates(self, result_candidates: list[Path]) -> list[Path]:
        candidates: list[Path] = []
        for result_path in result_candidates:
            sidecar_path = result_path.parent / SKILL_RUN_FEEDBACK_FILENAME
            if self._is_bundleable_feedback_sidecar(sidecar_path):
                candidates.append(sidecar_path)
        return candidates

    def _is_bundleable_feedback_sidecar(self, path: Path) -> bool:
        try:
            if not path.exists() or not path.is_file():
                return False
            with path.open("rb"):
                return True
        except OSError:
            return False

    def _artifact_candidates_from_result(
        self,
        run_dir: Path,
        result_path: Path,
    ) -> list[Path]:
        candidates: list[Path] = []
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return candidates
        artifacts_obj = payload.get("artifacts")
        if not isinstance(artifacts_obj, list):
            return candidates
        run_dir_resolved = run_dir.resolve()
        for rel_path in artifacts_obj:
            if not isinstance(rel_path, str) or not rel_path.strip():
                raise BundleAssemblyError(
                    code=BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID,
                    message="result artifacts must contain non-empty workspace-relative path strings",
                    path=str(rel_path),
                )
            rel_path = rel_path.strip()
            normalized = PurePosixPath(rel_path.replace("\\", "/"))
            if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
                raise BundleAssemblyError(
                    code=BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID,
                    message="result artifact path must be workspace-relative",
                    path=rel_path,
                )
            path = (run_dir / rel_path).resolve()
            try:
                path.relative_to(run_dir_resolved)
            except ValueError:
                raise BundleAssemblyError(
                    code=BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID,
                    message="result artifact path escapes the workspace",
                    path=rel_path,
                )
            if not path.exists() or not path.is_file():
                raise BundleAssemblyError(
                    code=BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING,
                    message="result artifact path does not reference an existing file",
                    path=rel_path,
                )
            candidates.append(path)
        return candidates

    def _dedupe_candidates(self, run_dir: Path, candidates: list[Path]) -> list[Path]:
        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            rel = path.relative_to(run_dir).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            unique.append(path)
        return unique

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True

    def hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
