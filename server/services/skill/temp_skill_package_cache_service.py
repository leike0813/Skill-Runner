from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from server.config import config
from server.models import SkillManifest
from server.services.engine_management.engine_policy import apply_engine_policy_to_manifest
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts
from server.services.orchestration.run_store import run_store
from server.services.platform.cache_key_builder import compute_skill_package_hash
from server.services.skill.skill_package_validator import SkillPackageValidator


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedTempSkillPackage:
    skill: SkillManifest
    skill_package_hash: str
    snapshot_dir: Path


class TempSkillPackageCacheService:
    """Caches validated temporary skill package snapshots by normalized content hash."""

    def __init__(self) -> None:
        self.validator = SkillPackageValidator()

    async def prepare_package(self, package_bytes: bytes, *, run_store_backend=None) -> CachedTempSkillPackage:
        store = run_store_backend or run_store
        self._validate_package_size(package_bytes)
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
                skill_dir,
                top_level,
                require_version=False,
            )
            self._strip_git_metadata(skill_dir)
            skill_package_hash = compute_skill_package_hash(skill_dir)
            if not skill_package_hash:
                raise ValueError("Temporary skill package hash is empty")

            snapshot_dir = self._snapshot_dir(skill_package_hash)
            cached = await store.get_temp_skill_package_cache(skill_package_hash)
            if cached and snapshot_dir.exists():
                await self._touch(skill_package_hash, run_store_backend=store)
                return CachedTempSkillPackage(
                    skill=self._load_manifest(snapshot_dir),
                    skill_package_hash=skill_package_hash,
                    snapshot_dir=snapshot_dir,
                )

            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_dir, snapshot_dir)
            manifest = self._load_manifest(snapshot_dir)
            if manifest.id != skill_id:
                raise ValueError("Skill identity mismatch after cache materialization")
            await self._record(
                manifest=manifest,
                skill_package_hash=skill_package_hash,
                snapshot_dir=snapshot_dir,
                run_store_backend=store,
            )
            return CachedTempSkillPackage(
                skill=manifest,
                skill_package_hash=skill_package_hash,
                snapshot_dir=snapshot_dir,
            )

    async def cleanup_expired(self, *, run_store_backend=None) -> int:
        store = run_store_backend or run_store
        now_iso = datetime.utcnow().isoformat()
        expired = await store.list_expired_temp_skill_package_cache(now_iso=now_iso)
        removed = 0
        for row in expired:
            skill_package_hash = str(row.get("skill_package_hash") or "")
            snapshot_path = row.get("snapshot_path")
            if isinstance(snapshot_path, str) and snapshot_path:
                cache_dir = Path(snapshot_path).parent
                shutil.rmtree(cache_dir, ignore_errors=True)
            if skill_package_hash:
                await store.delete_temp_skill_package_cache(skill_package_hash)
            removed += 1
        if removed:
            logger.info("Removed expired temp skill package cache entries=%s", removed)
        return removed

    def _validate_package_size(self, package_bytes: bytes) -> None:
        max_bytes = int(config.SYSTEM.TEMP_SKILL_PACKAGE_MAX_BYTES)
        if max_bytes > 0 and len(package_bytes) > max_bytes:
            raise ValueError(f"Skill package exceeds size limit ({max_bytes} bytes)")
        if not package_bytes:
            raise ValueError("Uploaded skill package is empty")

    def _snapshot_dir(self, skill_package_hash: str) -> Path:
        return Path(config.SYSTEM.TEMP_SKILL_PACKAGE_CACHE_DIR) / skill_package_hash / "snapshot"

    async def _touch(self, skill_package_hash: str, *, run_store_backend) -> None:
        await run_store_backend.touch_temp_skill_package_cache(
            skill_package_hash,
            expires_at=self._expires_at(),
        )

    async def _record(
        self,
        *,
        manifest: SkillManifest,
        skill_package_hash: str,
        snapshot_dir: Path,
        run_store_backend,
    ) -> None:
        await run_store_backend.upsert_temp_skill_package_cache(
            skill_package_hash=skill_package_hash,
            skill_id=manifest.id,
            manifest=manifest.model_dump(mode="json"),
            snapshot_path=str(snapshot_dir),
            expires_at=self._expires_at(),
        )

    def _expires_at(self) -> str:
        ttl_days = int(config.SYSTEM.TEMP_SKILL_PACKAGE_CACHE_TTL_DAYS)
        return (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()

    def _load_manifest(self, skill_dir: Path) -> SkillManifest:
        runner_path = skill_dir / "assets" / "runner.json"
        try:
            data = json.loads(runner_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid assets/runner.json") from exc
        data = infer_manifest_artifacts(data, skill_dir)
        apply_engine_policy_to_manifest(data)
        return SkillManifest(**data, path=skill_dir)

    def _strip_git_metadata(self, skill_dir: Path) -> None:
        for git_path in sorted(skill_dir.rglob(".git"), key=lambda path: len(path.parts), reverse=True):
            if git_path.is_dir():
                shutil.rmtree(git_path, ignore_errors=True)
            elif git_path.exists():
                git_path.unlink(missing_ok=True)


temp_skill_package_cache_service = TempSkillPackageCacheService()
