#!/usr/bin/env python3
"""Update or verify the Skill-Runner project version."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib


SEMVER_RE = re.compile(
    r"^v?(?P<version>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))$"
)


class VersionError(ValueError):
    """Raised when version input or project metadata is invalid."""


def normalize_version(raw: str) -> str:
    match = SEMVER_RE.fullmatch(raw.strip())
    if not match:
        raise VersionError("version must be SemVer X.Y.Z, optionally prefixed with v")
    return match.group("version")


def read_project_version(pyproject_path: Path) -> str:
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VersionError(f"failed to read {pyproject_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise VersionError(f"invalid TOML in {pyproject_path}: {exc}") from exc

    project = payload.get("project")
    if not isinstance(project, dict):
        raise VersionError("[project] section is missing")
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise VersionError("[project].version is missing")
    return normalize_version(version)


def write_project_version(pyproject_path: Path, version: str) -> None:
    normalized = normalize_version(version)
    lines = pyproject_path.read_text(encoding="utf-8").splitlines(keepends=True)
    in_project = False
    replaced = False
    version_line_re = re.compile(r'^(?P<prefix>\s*version\s*=\s*)"[^"]*"(?P<suffix>\s*(?:#.*)?(?:\r?\n)?)$')

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = version_line_re.match(line)
        if match:
            lines[index] = f'{match.group("prefix")}"{normalized}"{match.group("suffix")}'
            replaced = True
            break

    if not replaced:
        raise VersionError("[project].version line was not found")
    pyproject_path.write_text("".join(lines), encoding="utf-8")


def check_tag(pyproject_path: Path, tag: str) -> None:
    expected = normalize_version(tag)
    actual = read_project_version(pyproject_path)
    if actual != expected:
        raise VersionError(f"tag v{expected} does not match pyproject version {actual}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update or verify Skill-Runner version.")
    parser.add_argument("version", nargs="?", help="New SemVer version, optionally prefixed with v.")
    parser.add_argument("--check-tag", help="Verify a vX.Y.Z tag matches pyproject.toml.")
    parser.add_argument(
        "--project-root",
        default=Path(__file__).resolve().parent.parent,
        type=Path,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    pyproject_path = args.project_root / "pyproject.toml"

    try:
        if args.check_tag:
            if args.version:
                raise VersionError("provide either a version or --check-tag, not both")
            check_tag(pyproject_path, args.check_tag)
            print(f"ok: tag {args.check_tag} matches pyproject version {read_project_version(pyproject_path)}")
            return 0

        if not args.version:
            raise VersionError("version is required unless --check-tag is used")
        version = normalize_version(args.version)
        write_project_version(pyproject_path, version)
        print(f"updated {pyproject_path} to {version}")
        return 0
    except VersionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
