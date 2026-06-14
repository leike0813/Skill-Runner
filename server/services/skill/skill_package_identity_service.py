from __future__ import annotations

import logging
from pathlib import Path

from server.models import SkillManifest
from server.services.orchestration.run_store import run_store
from server.services.platform.cache_key_builder import compute_skill_package_hash
from server.services.skill.skill_registry import is_builtin_skill_path, skill_registry


logger = logging.getLogger(__name__)


class SkillPackageIdentityService:
    """Refreshes normalized package identities for registry-visible skills."""

    async def get_or_refresh_hash(self, skill: SkillManifest, *, run_store_backend=None) -> str:
        if skill.path is None:
            return ""
        skill_package_hash = compute_skill_package_hash(Path(skill.path))
        if not skill_package_hash:
            return ""
        await self.record_identity(
            skill=skill,
            skill_package_hash=skill_package_hash,
            run_store_backend=run_store_backend,
        )
        return skill_package_hash

    async def record_identity(
        self,
        *,
        skill: SkillManifest,
        skill_package_hash: str,
        run_store_backend=None,
    ) -> None:
        if skill.path is None:
            return
        source = "builtin" if is_builtin_skill_path(Path(skill.path)) else "installed"
        store = run_store_backend or run_store
        await store.upsert_skill_package_identity(
            skill_id=skill.id,
            skill_package_hash=skill_package_hash,
            source=source,
            skill_path=str(Path(skill.path)),
            manifest=skill.model_dump(mode="json"),
        )

    async def refresh_all(self) -> None:
        refreshed = 0
        for skill in skill_registry.list_skills():
            try:
                if await self.get_or_refresh_hash(skill, run_store_backend=run_store):
                    refreshed += 1
            except (OSError, RuntimeError, ValueError, TypeError):
                logger.warning(
                    "Failed to refresh skill package identity for %s",
                    skill.id,
                    exc_info=True,
                )
        logger.info("Refreshed skill package identities=%s", refreshed)


skill_package_identity_service = SkillPackageIdentityService()
