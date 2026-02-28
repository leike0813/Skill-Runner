from pathlib import Path

import pytest

from server.services.skill.skill_browser import (
    PREVIEW_MAX_BYTES,
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)


def _build_tree(tmp_path: Path) -> Path:
    root = tmp_path / "skill-a"
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "runner.json").write_text("{}", encoding="utf-8")
    (root / "SKILL.md").write_text("# demo", encoding="utf-8")
    return root


def test_list_skill_entries_returns_structure(tmp_path: Path):
    root = _build_tree(tmp_path)
    entries = list_skill_entries(root)
    rel_paths = [entry["rel_path"] for entry in entries]
    assert "assets" in rel_paths
    assert "assets/runner.json" in rel_paths
    assert "SKILL.md" in rel_paths


def test_resolve_skill_file_path_enforces_root(tmp_path: Path):
    root = _build_tree(tmp_path)
    resolved = resolve_skill_file_path(root, "SKILL.md")
    assert resolved.name == "SKILL.md"

    with pytest.raises(ValueError):
        resolve_skill_file_path(root, "../../etc/passwd")

    with pytest.raises(FileNotFoundError):
        resolve_skill_file_path(root, "missing.txt")


def test_build_preview_payload_text_binary_and_size(tmp_path: Path):
    text_file = tmp_path / "t.txt"
    text_file.write_text("hello", encoding="utf-8")
    text_preview = build_preview_payload(text_file)
    assert text_preview["mode"] == "text"
    assert text_preview["content"] == "hello"

    binary_file = tmp_path / "b.bin"
    binary_file.write_bytes(b"\x00\x01\x02")
    binary_preview = build_preview_payload(binary_file)
    assert binary_preview["mode"] == "binary"
    assert binary_preview["meta"] == "无信息"

    large_file = tmp_path / "l.txt"
    large_file.write_text("x" * (PREVIEW_MAX_BYTES + 1), encoding="utf-8")
    large_preview = build_preview_payload(large_file)
    assert large_preview["mode"] == "too_large"


def test_build_preview_payload_gb18030_markdown_is_text(tmp_path: Path):
    md_file = tmp_path / "digest.md"
    content = "## TL;DR\n\n这是一个中文段落。"
    md_file.write_bytes(content.encode("gb18030"))
    preview = build_preview_payload(md_file)
    assert preview["mode"] == "text"
    assert "中文段落" in preview["content"]
