#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.agent_cli_manager import (  # noqa: E402
    AgentCliManager,
    format_auth_status_payload,
    format_status_payload,
)


logger = logging.getLogger("agent-manager")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Skill Runner agent CLIs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Only check current engine status")
    mode.add_argument("--check-auth", action="store_true", help="Only check engine auth/path status")
    mode.add_argument("--ensure", action="store_true", help="Install missing engines into managed prefix")
    mode.add_argument("--upgrade", action="store_true", help="Upgrade all engines")
    mode.add_argument(
        "--upgrade-engine",
        choices=["codex", "gemini", "iflow", "opencode"],
        help="Upgrade a single engine",
    )
    parser.add_argument(
        "--import-credentials",
        type=str,
        default="",
        help="Import authentication credentials from source root (engine-named subdirectories)",
    )
    parser.add_argument(
        "--status-file",
        type=str,
        default="",
        help="Optional custom status output file path",
    )
    return parser


def _write_status(manager: AgentCliManager, status_file: Path | None) -> dict:
    payload = format_status_payload(manager.collect_status())
    target = status_file or (manager.profile.data_dir / "agent_status.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Agent status written to %s", target)
    return payload


def _write_auth_status(manager: AgentCliManager, status_file: Path | None) -> dict:
    payload = format_auth_status_payload(manager.collect_auth_status())
    target = status_file or (manager.profile.data_dir / "agent_auth_status.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Agent auth status written to %s", target)
    return payload


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    manager = AgentCliManager()
    manager.ensure_layout()

    if args.import_credentials:
        imported = manager.import_credentials(Path(args.import_credentials))
        logger.info("Imported credentials: %s", imported)

    if args.check_auth:
        _write_auth_status(manager, Path(args.status_file).resolve() if args.status_file else None)
        return 0

    if args.ensure:
        results = manager.ensure_installed()
        for engine, result in results.items():
            if result.returncode != 0:
                logger.warning("Failed to install %s: exit=%s", engine, result.returncode)
    elif args.upgrade:
        results = manager.upgrade_all()
        failed = False
        for engine, result in results.items():
            if result.returncode != 0:
                failed = True
                logger.warning("Failed to upgrade %s: exit=%s", engine, result.returncode)
        if failed:
            _write_status(manager, Path(args.status_file).resolve() if args.status_file else None)
            return 1
    elif args.upgrade_engine:
        result = manager.upgrade_engine(args.upgrade_engine)
        if result.returncode != 0:
            logger.error("Failed to upgrade %s", args.upgrade_engine)
            _write_status(manager, Path(args.status_file).resolve() if args.status_file else None)
            return result.returncode or 1
        if result.stdout:
            logger.info(result.stdout.rstrip())
        if result.stderr:
            logger.info(result.stderr.rstrip())

    _write_status(manager, Path(args.status_file).resolve() if args.status_file else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
