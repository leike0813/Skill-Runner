#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.engine_management.runtime_profile import get_runtime_profile  # noqa: E402


EngineState = Literal["authenticated", "unauthenticated", "unknown"]
OverallState = Literal["authenticated", "unauthenticated", "mixed"]


@dataclass(frozen=True)
class EngineFiles:
    auth: Path
    normal: Path
    unauth: Path | None = None
    aux_auth: Path | None = None
    aux_normal: Path | None = None
    aux_unauth: Path | None = None


@dataclass(frozen=True)
class StateSnapshot:
    agent_home: Path
    codex: EngineState
    gemini: EngineState
    iflow: EngineState
    opencode: EngineState

    @property
    def overall(self) -> OverallState:
        states = {self.codex, self.gemini, self.iflow, self.opencode}
        if states == {"authenticated"}:
            return "authenticated"
        if states == {"unauthenticated"}:
            return "unauthenticated"
        return "mixed"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or toggle local Skill Runner agent credential fixtures."
    )
    parser.add_argument(
        "--agent-home",
        type=Path,
        default=None,
        help="Override agent-home path. Defaults to runtime profile agent_home.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--status",
        action="store_true",
        help="Only print the current aggregate auth state.",
    )
    mode.add_argument(
        "--toggle",
        action="store_true",
        help="Toggle between authenticated and unauthenticated fixture states.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned rename operations without applying them.",
    )
    return parser


def _engine_files(agent_home: Path) -> dict[str, EngineFiles]:
    return {
        "codex": EngineFiles(
            auth=agent_home / ".codex" / "auth.json",
            normal=agent_home / ".codex" / "auth.normal.json",
        ),
        "gemini": EngineFiles(
            auth=agent_home / ".gemini" / "oauth_creds.json",
            normal=agent_home / ".gemini" / "oauth_creds.normal.json",
            aux_auth=agent_home / ".gemini" / "google_accounts.json",
            aux_normal=agent_home / ".gemini" / "google_accounts.normal.json",
            aux_unauth=agent_home / ".gemini" / "google_accounts.unauth.json",
        ),
        "iflow": EngineFiles(
            auth=agent_home / ".iflow" / "oauth_creds.json",
            normal=agent_home / ".iflow" / "oauth_creds.normal.json",
            unauth=agent_home / ".iflow" / "oauth_creds.unauth.json",
        ),
        "opencode": EngineFiles(
            auth=agent_home / ".local" / "share" / "opencode" / "auth.json",
            normal=agent_home / ".local" / "share" / "opencode" / "auth.normal.json",
            unauth=agent_home / ".local" / "share" / "opencode" / "auth.unauth.json",
        ),
    }


def _detect_codex_state(files: EngineFiles) -> EngineState:
    if files.auth.exists():
        return "authenticated"
    if files.normal.exists():
        return "unauthenticated"
    return "unknown"


def _detect_gemini_state(files: EngineFiles) -> EngineState:
    if files.auth.exists():
        return "authenticated"
    if files.normal.exists():
        return "unauthenticated"
    return "unknown"


def _detect_swap_state(files: EngineFiles) -> EngineState:
    if files.auth.exists() and files.unauth and files.unauth.exists():
        return "authenticated"
    if files.auth.exists() and files.normal.exists():
        return "unauthenticated"
    return "unknown"


def build_snapshot(agent_home: Path) -> StateSnapshot:
    files = _engine_files(agent_home)
    return StateSnapshot(
        agent_home=agent_home,
        codex=_detect_codex_state(files["codex"]),
        gemini=_detect_gemini_state(files["gemini"]),
        iflow=_detect_swap_state(files["iflow"]),
        opencode=_detect_swap_state(files["opencode"]),
    )


def _print_snapshot(snapshot: StateSnapshot) -> None:
    print("=== Skill Runner Agent Auth State ===")
    print(f"Agent Home: {snapshot.agent_home}")
    print(f"Overall: {snapshot.overall}")
    print(f"  codex: {snapshot.codex}")
    print(f"  gemini: {snapshot.gemini}")
    print(f"  iflow: {snapshot.iflow}")
    print(f"  opencode: {snapshot.opencode}")


def _collect_known_paths(files: dict[str, EngineFiles]) -> set[Path]:
    known: set[Path] = set()
    for item in files.values():
        known.add(item.auth)
        known.add(item.normal)
        if item.unauth is not None:
            known.add(item.unauth)
        if item.aux_auth is not None:
            known.add(item.aux_auth)
        if item.aux_normal is not None:
            known.add(item.aux_normal)
        if item.aux_unauth is not None:
            known.add(item.aux_unauth)
    return known


def _snapshot_existing_paths(files: dict[str, EngineFiles]) -> set[Path]:
    return {path for path in _collect_known_paths(files) if path.exists()}


def _rename(src: Path, dst: Path, *, existing_paths: set[Path], dry_run: bool) -> None:
    if src not in existing_paths:
        raise RuntimeError(f"Required source file missing: {src}")
    if dst in existing_paths:
        raise RuntimeError(f"Refusing to overwrite existing file: {dst}")
    print(f"rename: {src} -> {dst}")
    existing_paths.remove(src)
    existing_paths.add(dst)
    if not dry_run:
        src.rename(dst)


def _require(path: Path | None, *, label: str) -> Path:
    if path is None:
        raise RuntimeError(f"Missing configured path for {label}")
    return path


def toggle(agent_home: Path, *, dry_run: bool) -> None:
    snapshot = build_snapshot(agent_home)
    _print_snapshot(snapshot)
    if snapshot.overall == "mixed":
        raise RuntimeError("Refusing to toggle from a mixed or incomplete auth state.")

    files = _engine_files(agent_home)
    print(f"Action: toggle -> {'unauthenticated' if snapshot.overall == 'authenticated' else 'authenticated'}")
    existing_paths = _snapshot_existing_paths(files)
    if snapshot.overall == "authenticated":
        _rename(files["codex"].auth, files["codex"].normal, existing_paths=existing_paths, dry_run=dry_run)
        _rename(files["gemini"].auth, files["gemini"].normal, existing_paths=existing_paths, dry_run=dry_run)
        _rename(
            _require(files["gemini"].aux_auth, label="gemini.aux_auth"),
            _require(files["gemini"].aux_normal, label="gemini.aux_normal"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(
            _require(files["gemini"].aux_unauth, label="gemini.aux_unauth"),
            _require(files["gemini"].aux_auth, label="gemini.aux_auth"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(files["iflow"].auth, files["iflow"].normal, existing_paths=existing_paths, dry_run=dry_run)
        _rename(
            _require(files["iflow"].unauth, label="iflow.unauth"),
            files["iflow"].auth,
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(files["opencode"].auth, files["opencode"].normal, existing_paths=existing_paths, dry_run=dry_run)
        _rename(
            _require(files["opencode"].unauth, label="opencode.unauth"),
            files["opencode"].auth,
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
    else:
        _rename(files["codex"].normal, files["codex"].auth, existing_paths=existing_paths, dry_run=dry_run)
        _rename(files["gemini"].normal, files["gemini"].auth, existing_paths=existing_paths, dry_run=dry_run)
        _rename(
            _require(files["gemini"].aux_auth, label="gemini.aux_auth"),
            _require(files["gemini"].aux_unauth, label="gemini.aux_unauth"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(
            _require(files["gemini"].aux_normal, label="gemini.aux_normal"),
            _require(files["gemini"].aux_auth, label="gemini.aux_auth"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(
            files["iflow"].auth,
            _require(files["iflow"].unauth, label="iflow.unauth"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(files["iflow"].normal, files["iflow"].auth, existing_paths=existing_paths, dry_run=dry_run)
        _rename(
            files["opencode"].auth,
            _require(files["opencode"].unauth, label="opencode.unauth"),
            existing_paths=existing_paths,
            dry_run=dry_run,
        )
        _rename(files["opencode"].normal, files["opencode"].auth, existing_paths=existing_paths, dry_run=dry_run)

    if dry_run:
        return
    print("=== Result ===")
    _print_snapshot(build_snapshot(agent_home))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    agent_home = (args.agent_home or get_runtime_profile().agent_home).resolve()

    if args.status:
        _print_snapshot(build_snapshot(agent_home))
        return 0

    toggle(agent_home, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
