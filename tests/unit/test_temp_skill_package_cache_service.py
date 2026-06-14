import io
import json
import zipfile
from pathlib import Path

import pytest

from server.config import config
from server.services.orchestration.run_store import RunStore
from server.services.skill.temp_skill_package_cache_service import TempSkillPackageCacheService


def _package_bytes(*, skill_id: str = "demo-temp", reverse_order: bool = False) -> bytes:
    runner = {
        "id": skill_id,
        "engines": ["gemini"],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
    }
    entries = [
        (f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n"),
        (f"{skill_id}/assets/runner.json", json.dumps(runner)),
        (f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}})),
        (f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}})),
        (f"{skill_id}/assets/output.schema.json", json.dumps({"type": "object", "properties": {}})),
    ]
    if reverse_order:
        entries = list(reversed(entries))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_temp_skill_package_cache_reuses_normalized_snapshot_for_repacked_zip(tmp_path: Path):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    service = TempSkillPackageCacheService()

    first = await service.prepare_package(_package_bytes(reverse_order=False), run_store_backend=store)
    first_row = await store.get_temp_skill_package_cache(first.skill_package_hash)
    second = await service.prepare_package(_package_bytes(reverse_order=True), run_store_backend=store)
    second_row = await store.get_temp_skill_package_cache(second.skill_package_hash)

    assert first.skill_package_hash == second.skill_package_hash
    assert first.snapshot_dir == second.snapshot_dir
    assert first_row is not None
    assert second_row is not None
    assert second_row["expires_at"] >= first_row["expires_at"]


@pytest.mark.asyncio
async def test_temp_skill_package_cache_cleanup_removes_expired_snapshot(tmp_path: Path):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    service = TempSkillPackageCacheService()
    cached = await service.prepare_package(_package_bytes(), run_store_backend=store)
    assert cached.snapshot_dir.exists()

    await store.upsert_temp_skill_package_cache(
        skill_package_hash=cached.skill_package_hash,
        skill_id=cached.skill.id,
        manifest=cached.skill.model_dump(mode="json"),
        snapshot_path=str(cached.snapshot_dir),
        expires_at="2000-01-01T00:00:00",
    )
    removed = await service.cleanup_expired(run_store_backend=store)

    assert removed == 1
    assert not cached.snapshot_dir.exists()
    assert await store.get_temp_skill_package_cache(cached.skill_package_hash) is None


@pytest.mark.asyncio
async def test_temp_skill_package_cached_snapshot_is_unpatched(tmp_path: Path):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    service = TempSkillPackageCacheService()
    cached = await service.prepare_package(_package_bytes(), run_store_backend=store)

    assert (cached.snapshot_dir / "SKILL.md").read_text(encoding="utf-8") == "---\nname: demo-temp\n---\n"
