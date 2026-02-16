import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from ..config import config
from ..models import RunStatus, SkillManifest
from .skill_package_validator import SkillPackageValidator
from .temp_skill_run_store import temp_skill_run_store
from .manifest_artifact_inference import infer_manifest_artifacts

logger = logging.getLogger(__name__)


class TempSkillRunManager:
    """Validates, stages, and cleans up temporary skill packages."""

    def __init__(self) -> None:
        self.validator = SkillPackageValidator()

    def create_request_dirs(self, request_id: str) -> Path:
        request_root = self.request_root(request_id)
        request_root.mkdir(parents=True, exist_ok=True)
        return request_root

    def request_root(self, request_id: str) -> Path:
        return Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / request_id

    def stage_skill_package(self, request_id: str, package_bytes: bytes) -> SkillManifest:
        max_bytes = int(config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES)
        if max_bytes > 0 and len(package_bytes) > max_bytes:
            raise ValueError(f"Skill package exceeds size limit ({max_bytes} bytes)")
        if not package_bytes:
            raise ValueError("Uploaded skill package is empty")

        request_root = self.create_request_dirs(request_id)
        package_path = request_root / "skill_package.zip"
        package_path.write_bytes(package_bytes)

        top_level = self.validator.inspect_zip_top_level_from_path(package_path)
        staged_root = request_root / "staged"
        self.validator.extract_zip_safe(package_path, staged_root)
        staged_skill_dir = staged_root / top_level
        if not staged_skill_dir.exists() or not staged_skill_dir.is_dir():
            raise ValueError("Skill package extraction failed")

        skill_id, _version = self.validator.validate_skill_dir(
            staged_skill_dir, top_level, require_version=False
        )

        manifest = self._load_manifest(staged_skill_dir)
        if not manifest.path:
            raise ValueError("Temporary skill path unavailable after staging")
        if manifest.id != skill_id:
            raise ValueError("Skill identity mismatch after manifest load")

        temp_skill_run_store.update_staged_skill(
            request_id,
            skill_id=skill_id,
            skill_package_path=str(package_path),
            staged_skill_dir=str(staged_skill_dir),
        )
        return manifest

    def cleanup_temp_assets(self, request_id: str) -> None:
        rec = temp_skill_run_store.get_request(request_id)
        if not rec:
            return
        package_path = rec.get("skill_package_path")
        staged_dir = rec.get("staged_skill_dir")
        if package_path:
            path = Path(package_path)
            if path.exists():
                path.unlink(missing_ok=True)
        if staged_dir:
            root = Path(staged_dir).parent
            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
        temp_skill_run_store.clear_temp_paths(request_id)

    def on_terminal(
        self,
        request_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
        debug_keep_temp: bool = False,
    ) -> None:
        temp_skill_run_store.update_status(request_id, status=status, error=error)
        if debug_keep_temp:
            return
        try:
            self.cleanup_temp_assets(request_id)
        except Exception:
            logger.warning(
                "Temporary skill cleanup failed for request %s; deferred to scheduled cleanup",
                request_id,
                exc_info=True,
            )

    async def cleanup_orphans(self) -> Dict[str, int]:
        retention_hours = int(config.SYSTEM.TEMP_SKILL_ORPHAN_RETENTION_HOURS)
        removed = 0
        candidates = temp_skill_run_store.list_orphan_candidates(retention_hours)
        for row in candidates:
            request_id = row["request_id"]
            try:
                self.cleanup_temp_assets(request_id)
                removed += 1
            except Exception:
                logger.warning("Failed orphan cleanup for temp request %s", request_id, exc_info=True)
        return {"removed": removed}

    def _load_manifest(self, skill_dir: Path) -> SkillManifest:
        runner_path = skill_dir / "assets" / "runner.json"
        try:
            data = json.loads(runner_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid assets/runner.json") from exc
        data = infer_manifest_artifacts(data, skill_dir)
        return SkillManifest(**data, path=skill_dir)


temp_skill_run_manager = TempSkillRunManager()
