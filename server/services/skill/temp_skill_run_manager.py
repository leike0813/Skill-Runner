from server.models import SkillManifest
from server.services.skill.temp_skill_package_cache_service import temp_skill_package_cache_service


class TempSkillRunManager:
    """Validates uploaded temporary skill packages."""

    async def inspect_skill_package(
        self,
        package_bytes: bytes,
    ) -> SkillManifest:
        cached = await temp_skill_package_cache_service.prepare_package(package_bytes)
        return cached.skill


temp_skill_run_manager = TempSkillRunManager()
