import json
from pathlib import Path

from server.models import SkillManifest
from server.services.cache_key_builder import (
    build_input_manifest,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_skill_fingerprint,
    compute_cache_key
)


def test_input_manifest_hash_changes_with_content(tmp_path):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    file_path = uploads_dir / "a.txt"
    file_path.write_text("one")

    manifest1 = build_input_manifest(uploads_dir)
    hash1 = compute_input_manifest_hash(manifest1)

    file_path.write_text("two")
    manifest2 = build_input_manifest(uploads_dir)
    hash2 = compute_input_manifest_hash(manifest2)

    assert hash1 != hash2


def test_skill_fingerprint_changes_with_files(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))

    skill = SkillManifest(id="demo", path=skill_dir, schemas={})
    fp1 = compute_skill_fingerprint(skill, "gemini")

    (skill_dir / "SKILL.md").write_text("v2")
    fp2 = compute_skill_fingerprint(skill, "gemini")

    assert fp1 != fp2


def test_cache_key_stable_for_same_inputs(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    skill = SkillManifest(id="demo", path=skill_dir, schemas={})

    skill_fp = compute_skill_fingerprint(skill, "gemini")
    cache_key1 = compute_cache_key(
        skill_id="demo",
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h"
    )
    cache_key2 = compute_cache_key(
        skill_id="demo",
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h"
    )
    assert cache_key1 == cache_key2


def test_input_manifest_empty_dir(tmp_path):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    manifest = build_input_manifest(uploads_dir)
    assert manifest["files"] == []


def test_inline_input_hash_changes_with_payload():
    hash1 = compute_inline_input_hash({"query": "one", "tags": ["a"]})
    hash2 = compute_inline_input_hash({"query": "two", "tags": ["a"]})
    assert hash1 != hash2


def test_inline_input_hash_empty_payload_is_blank():
    assert compute_inline_input_hash({}) == ""


def test_cache_key_changes_with_inline_input_hash(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    skill = SkillManifest(id="demo", path=skill_dir, schemas={})

    skill_fp = compute_skill_fingerprint(skill, "gemini")
    key1 = compute_cache_key(
        skill_id="demo",
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "one"}),
    )
    key2 = compute_cache_key(
        skill_id="demo",
        engine="gemini",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "two"}),
    )
    assert key1 != key2


def test_skill_fingerprint_engine_specific_config(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("base")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    (assets_dir / "gemini_settings.json").write_text(json.dumps({"model": "a"}))
    (assets_dir / "iflow_settings.json").write_text(json.dumps({"modelName": "b"}))
    (assets_dir / "codex_config.toml").write_text("model = 'c'")

    skill = SkillManifest(id="demo", path=skill_dir, schemas={})
    gemini_fp = compute_skill_fingerprint(skill, "gemini")
    iflow_fp = compute_skill_fingerprint(skill, "iflow")
    codex_fp = compute_skill_fingerprint(skill, "codex")

    assert gemini_fp != iflow_fp
    assert iflow_fp != codex_fp


def test_skill_fingerprint_without_path_returns_empty():
    skill = SkillManifest(id="demo", path=None, schemas={})
    assert compute_skill_fingerprint(skill, "gemini") == ""


def test_input_manifest_missing_dir():
    manifest = build_input_manifest(Path("does-not-exist"))
    assert manifest["files"] == []
