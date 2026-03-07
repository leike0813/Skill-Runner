#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.services.platform.data_reset_service import DataResetOptions, ResetTargets, data_reset_service


def _print_targets(targets: ResetTargets, dry_run: bool) -> None:
    print("=== Skill Runner Data Reset ===")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"Data dir: {targets.data_dir}")
    print("SQLite files:")
    for path in targets.db_files:
        print(f"  - {path}")
    print("Data directories:")
    for path in targets.data_dirs:
        print(f"  - {path}")
    if targets.optional_paths:
        print("Optional paths:")
        for path in targets.optional_paths:
            print(f"  - {path}")
    else:
        print("Optional paths: (none)")
    print("===============================")


def _confirm_or_exit(yes: bool) -> None:
    if yes:
        return
    answer = input("Continue and delete the paths above? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset Skill Runner databases and related persisted data."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned deletions without applying them.",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Also clear LOG_DIR (global app logs).",
    )
    parser.add_argument(
        "--include-engine-catalog",
        action="store_true",
        help="Also remove engine model catalog cache files.",
    )
    parser.add_argument(
        "--include-engine-auth-sessions",
        action="store_true",
        help="Also remove data/engine_auth_sessions (auth observability logs).",
    )
    args = parser.parse_args()

    options = DataResetOptions(
        include_logs=args.include_logs,
        include_engine_catalog=args.include_engine_catalog,
        include_engine_auth_sessions=args.include_engine_auth_sessions,
        dry_run=args.dry_run,
    )
    targets = data_reset_service.build_targets(options)
    _print_targets(targets, dry_run=args.dry_run)

    if args.dry_run:
        return 0

    _confirm_or_exit(args.yes)
    result = data_reset_service.execute_reset(options)
    for item in result.path_results:
        status = "deleted" if item.deleted else "missing"
        print(f"[{status}] {item.path}")

    print(
        "Reset complete: "
        "deleted="
        f"{result.deleted_count}, "
        f"missing={result.missing_count}, "
        f"recreated={result.recreated_count}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
