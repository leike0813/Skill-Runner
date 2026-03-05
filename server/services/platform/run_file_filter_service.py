from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath


ALLOWLIST_NON_DEBUG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "policy" / "run_bundle_allowlist_non_debug.ignore"
)
DENYLIST_DEBUG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "policy" / "run_bundle_denylist_debug.ignore"
)


def normalize_relative_path(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("invalid path")
    for part in candidate.parts:
        if part in {"", ".", ".."}:
            raise ValueError("invalid path")
    normalized = candidate.as_posix().rstrip("/")
    if not normalized:
        raise ValueError("invalid path")
    return normalized


def _load_patterns(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        lines.append(cleaned)
    return tuple(lines)


@dataclass(frozen=True)
class _PatternSet:
    patterns: tuple[str, ...]

    def matches(self, rel_path: str, *, is_dir: bool) -> bool:
        _ = is_dir
        normalized = normalize_relative_path(rel_path)
        file_candidate = normalized
        dir_candidate = f"{normalized}/"
        for pattern in self.patterns:
            anchored = pattern.lstrip("/")
            if fnmatchcase(file_candidate, anchored):
                return True
            if fnmatchcase(dir_candidate, anchored):
                return True
        return False


class RunFileFilterService:
    def __init__(
        self,
        *,
        allowlist_path: Path = ALLOWLIST_NON_DEBUG_PATH,
        denylist_path: Path = DENYLIST_DEBUG_PATH,
    ) -> None:
        self._allowlist = _PatternSet(patterns=_load_patterns(allowlist_path))
        self._denylist = _PatternSet(patterns=_load_patterns(denylist_path))

    def include_in_non_debug_bundle(self, rel_path: str) -> bool:
        return self._allowlist.matches(rel_path, is_dir=False)

    def include_in_debug_bundle(self, rel_path: str) -> bool:
        return not self._denylist.matches(rel_path, is_dir=False)

    def include_in_run_explorer(self, rel_path: str, *, is_dir: bool) -> bool:
        return not self._denylist.matches(rel_path, is_dir=is_dir)

    def path_allowed_for_run_explorer(self, rel_path: str) -> bool:
        normalized = normalize_relative_path(rel_path)
        parent = PurePosixPath(normalized).parent
        if not self.include_in_run_explorer(normalized, is_dir=False):
            return False
        while str(parent) not in {"", "."}:
            if not self.include_in_run_explorer(parent.as_posix(), is_dir=True):
                return False
            parent = parent.parent
        return True


run_file_filter_service = RunFileFilterService()
