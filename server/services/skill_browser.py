from pathlib import Path
from typing import Any


PREVIEW_MAX_BYTES = 256 * 1024


def list_skill_entries(skill_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def _walk(current: Path, depth: int) -> None:
        children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for child in children:
            rel = child.relative_to(skill_root).as_posix()
            is_dir = child.is_dir() and not child.is_symlink()
            entries.append(
                {
                    "rel_path": rel,
                    "name": child.name,
                    "is_dir": is_dir,
                    "depth": depth,
                }
            )
            if is_dir:
                _walk(child, depth + 1)

    _walk(skill_root, 0)
    return entries


def resolve_skill_file_path(skill_root: Path, relative_path: str) -> Path:
    path_text = relative_path.strip()
    if not path_text:
        raise ValueError("path is required")

    requested = Path(path_text)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("invalid path")

    root_resolved = skill_root.resolve(strict=True)
    candidate = (skill_root / requested).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path escapes skill root") from exc

    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("file not found")

    candidate_resolved = candidate.resolve(strict=True)
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path escapes skill root") from exc

    return candidate_resolved


def build_preview_payload(file_path: Path) -> dict[str, Any]:
    size = file_path.stat().st_size
    if size > PREVIEW_MAX_BYTES:
        return {
            "mode": "too_large",
            "content": None,
            "size": size,
            "meta": "无信息",
        }

    raw = file_path.read_bytes()
    if _is_binary(raw):
        return {
            "mode": "binary",
            "content": None,
            "size": size,
            "meta": "无信息",
        }

    return {
        "mode": "text",
        "content": raw.decode("utf-8", errors="replace"),
        "size": size,
        "meta": f"{size} bytes, utf-8",
    }


def _is_binary(data: bytes) -> bool:
    sample = data[:4096]
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False
