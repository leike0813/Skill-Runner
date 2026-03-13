#!/usr/bin/env python3
"""Generate release integrity manifest for preflight checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED_DIR_NAMES = {".git", "dist", ".pytest_cache", ".mypy_cache", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
CORE_DIRS = ("server", "scripts")
CORE_FILES = ("pyproject.toml", "uv.lock", "docker-compose.yml")


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
        return True
    return path.suffix.lower() in EXCLUDED_SUFFIXES


def _collect_files(root: Path) -> list[Path]:
    selected: set[Path] = set()
    for rel_dir in CORE_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _is_excluded(rel):
                continue
            selected.add(rel)
    for rel_file in CORE_FILES:
        file_path = root / rel_file
        if file_path.is_file():
            rel = file_path.relative_to(root)
            if not _is_excluded(rel):
                selected.add(rel)
    return sorted(selected)


def generate_manifest(root: Path, output_path: Path) -> None:
    files_payload = []
    for rel_path in _collect_files(root):
        abs_path = root / rel_path
        sha256_hex, size = _sha256_file(abs_path)
        files_payload.append(
            {
                "path": rel_path.as_posix(),
                "sha256": sha256_hex,
                "size": size,
            }
        )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": {
            "directories": list(CORE_DIRS),
            "files": list(CORE_FILES),
        },
        "files": files_payload,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate release integrity manifest.")
    parser.add_argument("--root", default=".", help="Project root to scan.")
    parser.add_argument("--output", required=True, help="Output manifest path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    output_path = Path(args.output).resolve()
    generate_manifest(root, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
