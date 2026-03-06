import json
import tempfile
from pathlib import Path

from server.config import config
from server.models import SkillManifest
from server.services.engine_management.engine_policy import apply_engine_policy_to_manifest
from .skill_package_validator import SkillPackageValidator
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts


class TempSkillRunManager:
    """Validates uploaded temporary skill packages."""

    def __init__(self) -> None:
        self.validator = SkillPackageValidator()

    async def inspect_skill_package(
        self,
        package_bytes: bytes,
    ) -> SkillManifest:
        max_bytes = int(config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES)
        if max_bytes > 0 and len(package_bytes) > max_bytes:
            raise ValueError(f"Skill package exceeds size limit ({max_bytes} bytes)")
        if not package_bytes:
            raise ValueError("Uploaded skill package is empty")

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            package_path = tmp_dir / "skill_package.zip"
            package_path.write_bytes(package_bytes)

            top_level = self.validator.inspect_zip_top_level_from_path(package_path)
            extract_root = tmp_dir / "extract"
            self.validator.extract_zip_safe(package_path, extract_root)
            skill_dir = extract_root / top_level
            if not skill_dir.exists() or not skill_dir.is_dir():
                raise ValueError("Skill package extraction failed")

            skill_id, _version = self.validator.validate_skill_dir(
                skill_dir, top_level, require_version=False
            )

            manifest = self._load_manifest(skill_dir)
            if not manifest.path:
                raise ValueError("Temporary skill path unavailable after inspection")
            if manifest.id != skill_id:
                raise ValueError("Skill identity mismatch after manifest load")

        return manifest

    def _load_manifest(self, skill_dir: Path) -> SkillManifest:
        runner_path = skill_dir / "assets" / "runner.json"
        try:
            data = json.loads(runner_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid assets/runner.json") from exc
        data = infer_manifest_artifacts(data, skill_dir)
        apply_engine_policy_to_manifest(data)
        return SkillManifest(**data, path=skill_dir)


temp_skill_run_manager = TempSkillRunManager()
