from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

from server.models import RunLocalSkillRef, RunLocalSkillSource, SkillManifest
from server.services.engine_management.engine_policy import apply_engine_policy_to_manifest
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts
from server.services.skill.skill_package_validator import SkillPackageValidator
from server.services.skill.skill_patcher import skill_patcher


class RunFolderBootstrapper:
    """Materialize a canonical run-local skill snapshot during create-run."""

    def __init__(self) -> None:
        self._validator = SkillPackageValidator()

    def snapshot_dir(self, *, run_dir: Path, engine_name: str, skill_id: str) -> Path:
        return run_dir / f".{engine_name}" / "skills" / skill_id

    def materialize_skill(
        self,
        *,
        skill: SkillManifest,
        run_dir: Path,
        engine_name: str,
        execution_mode: str,
        source: RunLocalSkillSource,
    ) -> RunLocalSkillRef:
        snapshot_dir = self.snapshot_dir(run_dir=run_dir, engine_name=engine_name, skill_id=skill.id)
        self._materialize_installed_skill(
            skill=skill,
            snapshot_dir=snapshot_dir,
            execution_mode=execution_mode,
        )
        return RunLocalSkillRef(
            skill_id=skill.id,
            engine=engine_name,
            snapshot_dir=snapshot_dir,
            source=source,
        )

    def materialize_temp_skill_package(
        self,
        *,
        package_bytes: bytes,
        run_dir: Path,
        engine_name: str,
        execution_mode: str,
        source: RunLocalSkillSource,
    ) -> tuple[SkillManifest, RunLocalSkillRef]:
        top_level = self._validator.inspect_zip_top_level_from_bytes(package_bytes)
        snapshot_dir = self.snapshot_dir(
            run_dir=run_dir,
            engine_name=engine_name,
            skill_id=top_level,
        )
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(package_bytes), "r") as zf:
                snapshot_root = snapshot_dir.resolve()
                prefix = f"{top_level}/"
                for member in zf.infolist():
                    clean = member.filename.strip("/")
                    if not clean or clean.startswith("__MACOSX/"):
                        continue
                    self._validate_zip_entry(clean)
                    if clean == top_level:
                        continue
                    if not clean.startswith(prefix):
                        raise ValueError("Skill package must contain exactly one top-level directory")
                    relative = clean[len(prefix):]
                    if not relative:
                        continue
                    out_path = (snapshot_dir / relative).resolve()
                    if not str(out_path).startswith(str(snapshot_root)):
                        raise ValueError(f"Unsafe zip entry path: {clean}")
                    if member.is_dir():
                        out_path.mkdir(parents=True, exist_ok=True)
                        continue
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            self._validator.validate_skill_dir(
                snapshot_dir,
                top_level,
                require_version=False,
            )
            manifest = self._load_manifest(snapshot_dir)
            self._patch_materialized_dir(
                skill=manifest,
                snapshot_dir=snapshot_dir,
                execution_mode=execution_mode,
            )
            return (
                manifest,
                RunLocalSkillRef(
                    skill_id=manifest.id,
                    engine=engine_name,
                    snapshot_dir=snapshot_dir,
                    source=source,
                ),
            )
        except Exception:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise

    def load_from_snapshot(
        self,
        *,
        run_dir: Path,
        skill_id: str,
        engine_name: str,
    ) -> SkillManifest | None:
        snapshot_dir = self.snapshot_dir(run_dir=run_dir, engine_name=engine_name, skill_id=skill_id)
        runner_json = snapshot_dir / "assets" / "runner.json"
        if not runner_json.exists():
            return None
        try:
            data = json.loads(runner_json.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        data = infer_manifest_artifacts(data, snapshot_dir)
        apply_engine_policy_to_manifest(data)
        return SkillManifest(**data, path=snapshot_dir)

    def _load_manifest(self, skill_dir: Path) -> SkillManifest:
        runner_json = skill_dir / "assets" / "runner.json"
        data = json.loads(runner_json.read_text(encoding="utf-8"))
        data = infer_manifest_artifacts(data, skill_dir)
        apply_engine_policy_to_manifest(data)
        return SkillManifest(**data, path=skill_dir)

    def _materialize_installed_skill(
        self,
        *,
        skill: SkillManifest,
        snapshot_dir: Path,
        execution_mode: str,
    ) -> None:
        if skill.path is None:
            raise RuntimeError(f"Cannot bootstrap run folder for '{skill.id}' without a source path")
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        try:
            shutil.copytree(skill.path, snapshot_dir)
        except (OSError, shutil.Error) as exc:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to bootstrap run folder for '{skill.id}'") from exc
        self._patch_materialized_dir(
            skill=skill,
            snapshot_dir=snapshot_dir,
            execution_mode=execution_mode,
        )

    def _patch_materialized_dir(
        self,
        *,
        skill: SkillManifest,
        snapshot_dir: Path,
        execution_mode: str,
    ) -> None:
        output_schema_relpath = (
            str(skill.schemas.get("output"))
            if isinstance(skill.schemas, dict) and isinstance(skill.schemas.get("output"), str)
            else None
        )
        output_schema = skill_patcher.load_output_schema(
            skill_path=snapshot_dir,
            output_schema_relpath=output_schema_relpath,
        )
        skill_patcher.patch_skill_md(
            snapshot_dir,
            list(skill.artifacts or []),
            execution_mode=execution_mode,
            output_schema=output_schema,
        )

    def _validate_zip_entry(self, clean_name: str) -> None:
        entry = Path(clean_name)
        if entry.is_absolute() or clean_name.startswith("/") or clean_name.startswith("\\"):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
        if any(part == ".." for part in entry.parts):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
        if entry.parts and entry.parts[0].endswith(":"):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")

run_folder_bootstrapper = RunFolderBootstrapper()
