import json
from pathlib import Path

from server.models import SkillManifest
from server.services.platform.cache_key_builder import (
    build_input_manifest,
    compute_bytes_hash,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_skill_fingerprint,
    compute_skill_package_hash,
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
    fp1 = compute_skill_fingerprint(skill, "qwen")

    (skill_dir / "SKILL.md").write_text("v2")
    fp2 = compute_skill_fingerprint(skill, "qwen")

    assert fp1 != fp2


def test_cache_key_stable_for_same_inputs(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    skill = SkillManifest(id="demo", path=skill_dir, schemas={})

    skill_fp = compute_skill_fingerprint(skill, "qwen")
    cache_key1 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h"
    )
    cache_key2 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
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

    skill_fp = compute_skill_fingerprint(skill, "qwen")
    key1 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "one"}),
    )
    key2 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "two"}),
    )
    assert key1 != key2


def test_cache_key_changes_with_workspace_input_token(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    skill = SkillManifest(id="demo", path=skill_dir, schemas={})

    skill_fp = compute_skill_fingerprint(skill, "qwen")
    key1 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        workspace_input_token="workspace-a",
    )
    key2 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        skill_fingerprint=skill_fp,
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        workspace_input_token="workspace-b",
    )
    assert key1 != key2


def test_cache_key_changes_only_when_skill_run_feedback_enabled():
    base_key = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
    )
    false_key = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        collect_skill_run_feedback=False,
    )
    true_key = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        collect_skill_run_feedback=True,
    )
    assert false_key == base_key
    assert true_key != base_key


def test_skill_fingerprint_engine_specific_config(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("base")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    (assets_dir / "qwen_config.json").write_text(json.dumps({"model": {"name": "b"}}))
    (assets_dir / "codex_config.toml").write_text("model = 'c'")
    (assets_dir / "opencode_config.json").write_text(json.dumps({"sandbox": "workspace-write"}))

    skill = SkillManifest(id="demo", path=skill_dir, schemas={})
    qwen_fp = compute_skill_fingerprint(skill, "qwen")
    codex_fp = compute_skill_fingerprint(skill, "codex")
    opencode_fp = compute_skill_fingerprint(skill, "opencode")

    assert qwen_fp != codex_fp
    assert codex_fp != opencode_fp


def test_skill_fingerprint_uses_declared_engine_config_override(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("base")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "engine_configs": {"qwen": "custom/gemini_settings.json"},
            }
        )
    )
    custom_dir = skill_dir / "custom"
    custom_dir.mkdir()
    (custom_dir / "gemini_settings.json").write_text(json.dumps({"model": "declared"}))
    (assets_dir / "gemini_settings.json").write_text(json.dumps({"model": "fallback"}))

    skill = SkillManifest(
        id="demo",
        path=skill_dir,
        schemas={},
        engine_configs={"qwen": "custom/gemini_settings.json"},
    )
    original = compute_skill_fingerprint(skill, "qwen")

    (custom_dir / "gemini_settings.json").write_text(json.dumps({"model": "declared-2"}))
    updated = compute_skill_fingerprint(skill, "qwen")

    assert original != updated


def test_skill_fingerprint_uses_schema_fallback_assets(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("base")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo", "schemas": {}}))
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {"a": {"type": "string"}}}))

    skill = SkillManifest(id="demo", path=skill_dir, schemas={})
    original = compute_skill_fingerprint(skill, "qwen")

    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object", "properties": {"b": {"type": "string"}}}))
    updated = compute_skill_fingerprint(skill, "qwen")

    assert original != updated


def test_skill_fingerprint_without_path_returns_empty():
    skill = SkillManifest(id="demo", path=None, schemas={})
    assert compute_skill_fingerprint(skill, "qwen") == ""


def test_input_manifest_missing_dir():
    manifest = build_input_manifest(Path("does-not-exist"))
    assert manifest["files"] == []


def test_compute_bytes_hash_changes_with_content():
    assert compute_bytes_hash(b"one") != compute_bytes_hash(b"two")


def test_skill_package_hash_changes_with_content_but_ignores_git_metadata(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    git_dir = skill_dir / ".git"
    assets_dir.mkdir(parents=True)
    git_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    (git_dir / "HEAD").write_text("ignored")

    original = compute_skill_package_hash(skill_dir)
    (git_dir / "HEAD").write_text("still ignored")
    assert compute_skill_package_hash(skill_dir) == original

    (skill_dir / "SKILL.md").write_text("v2")
    assert compute_skill_package_hash(skill_dir) != original


def test_cache_key_changes_with_skill_package_hash(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    package_hash_v1 = compute_skill_package_hash(skill_dir)
    (skill_dir / "SKILL.md").write_text("v2")
    package_hash_v2 = compute_skill_package_hash(skill_dir)

    key1 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        skill_package_hash=package_hash_v1,
    )
    key2 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        skill_package_hash=package_hash_v2,
    )
    assert key1 != key2


def test_cache_key_stable_for_installed_and_temp_with_same_package_hash(tmp_path):
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("v1")
    (assets_dir / "runner.json").write_text(json.dumps({"id": "demo"}))
    package_hash = compute_skill_package_hash(skill_dir)

    key1 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "same"}),
        skill_package_hash=package_hash,
    )
    key2 = compute_cache_key(
        skill_id="demo",
        engine="qwen",
        parameter={"a": 1},
        engine_options={"model": "x"},
        input_manifest_hash="h",
        inline_input_hash=compute_inline_input_hash({"query": "same"}),
        skill_package_hash=package_hash,
    )
    assert key1 == key2
