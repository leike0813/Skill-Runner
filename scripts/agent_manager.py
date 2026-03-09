#!/usr/bin/env python3
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services.engine_management.agent_cli_manager import (  # noqa: E402
    AgentCliManager,
    format_auth_status_payload,
    format_status_payload,
)
from server.services.engine_management.engine_status_cache_service import (  # noqa: E402
    EngineStatusCacheService,
)


logger = logging.getLogger("agent-manager")
_SENSITIVE_KV_PATTERN = re.compile(
    r"(?i)\b(token|access_token|refresh_token|client_secret|secret|password|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


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
        "--status-file",
        type=str,
        default="",
        help="Optional custom status output file path",
    )
    parser.add_argument(
        "--bootstrap-report-file",
        type=str,
        default="",
        help="Optional bootstrap diagnostics report path (JSON)",
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask_sensitive(text: str) -> str:
    if not text:
        return ""
    return _SENSITIVE_KV_PATTERN.sub(r"\1=***", text)


def _summarize_output(text: str, *, max_lines: int = 8, max_chars: int = 800) -> str:
    cleaned = _mask_sensitive((text or "").strip())
    if not cleaned:
        return ""
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) > max_lines:
        head = max_lines // 2
        tail = max_lines - head
        lines = lines[:head] + ["..."] + lines[-tail:]
    summary = "\n".join(lines).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 14].rstrip() + "...(truncated)"
    return summary


def _compact_for_log(summary: str, *, max_chars: int = 220) -> str:
    if not summary:
        return ""
    compact = " ".join(summary.split())
    if len(compact) > max_chars:
        return compact[: max_chars - 14] + "...(truncated)"
    return compact


def _write_bootstrap_report(report_file: Path | None, payload: dict[str, Any]) -> None:
    if report_file is None:
        return
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Bootstrap diagnostics report written to %s", report_file)


def _write_status(manager: AgentCliManager, status_file: Path | None) -> dict:
    payload = format_status_payload(manager.collect_status())
    cache_service = EngineStatusCacheService(manager)
    asyncio.run(cache_service.write_payload(payload))
    logger.info(
        "Agent status cache updated in %s (table=engine_status_cache)",
        cache_service.db_path,
    )
    if status_file is not None:
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        logger.info("Agent status exported to %s", status_file)
    return payload


def _write_auth_status(manager: AgentCliManager, status_file: Path | None) -> dict:
    payload = format_auth_status_payload(manager.collect_auth_status())
    target = status_file or (manager.profile.data_dir / "agent_auth_status.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Agent auth status written to %s", target)
    return payload


def _ensure_with_diagnostics(manager: AgentCliManager) -> dict[str, Any]:
    engines_payload: dict[str, Any] = {}
    failed_engines: list[str] = []
    started_at = time.perf_counter()
    for engine in manager.supported_engines():
        engine_started_at = time.perf_counter()
        managed_before = manager.resolve_managed_engine_command(engine)
        payload: dict[str, Any] = {
            "engine": engine,
            "attempted_install": False,
            "managed_present_before": managed_before is not None,
            "managed_cli_path_before": str(managed_before) if managed_before else None,
            "managed_present_after": managed_before is not None,
            "managed_cli_path_after": str(managed_before) if managed_before else None,
            "package": None,
            "exit_code": None,
            "stdout_summary": "",
            "stderr_summary": "",
            "duration_ms": 0,
            "outcome": "already_present" if managed_before else "pending",
        }
        if managed_before is None:
            package = manager.engine_package(engine)
            payload["package"] = package
            payload["attempted_install"] = True
            logger.info(
                "event=agent.install.start phase=agent_ensure engine=%s package=%s outcome=running",
                engine,
                package,
            )
            result = manager.install_package(package)
            payload["exit_code"] = int(result.returncode)
            payload["stdout_summary"] = _summarize_output(result.stdout)
            payload["stderr_summary"] = _summarize_output(result.stderr)
            managed_after = manager.resolve_managed_engine_command(engine)
            payload["managed_present_after"] = managed_after is not None
            payload["managed_cli_path_after"] = str(managed_after) if managed_after else None
            if result.returncode == 0:
                payload["outcome"] = "installed"
                logger.info(
                    "event=agent.install.result phase=agent_ensure engine=%s outcome=installed exit_code=%s duration_ms=%s",
                    engine,
                    payload["exit_code"],
                    int((time.perf_counter() - engine_started_at) * 1000),
                )
            else:
                payload["outcome"] = "install_failed"
                failed_engines.append(engine)
                logger.warning(
                    "event=agent.install.result phase=agent_ensure engine=%s outcome=failed exit_code=%s duration_ms=%s stderr_summary=%s",
                    engine,
                    payload["exit_code"],
                    int((time.perf_counter() - engine_started_at) * 1000),
                    _compact_for_log(payload["stderr_summary"]),
                )
        payload["duration_ms"] = int((time.perf_counter() - engine_started_at) * 1000)
        engines_payload[engine] = payload
        if payload["outcome"] == "already_present":
            logger.info(
                "event=agent.install.result phase=agent_ensure engine=%s outcome=already_present duration_ms=%s",
                engine,
                payload["duration_ms"],
            )

    outcome = "ok" if not failed_engines else "partial_failure"
    total_duration_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "event=agent.ensure.summary phase=agent_ensure outcome=%s total_duration_ms=%s failed_engines=%s",
        outcome,
        total_duration_ms,
        ",".join(failed_engines) if failed_engines else "none",
    )
    return {
        "generated_at": _utc_now_iso(),
        "summary": {
            "outcome": outcome,
            "engines_total": len(manager.supported_engines()),
            "failed_engines": failed_engines,
            "total_duration_ms": total_duration_ms,
        },
        "engines": engines_payload,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_parser()
    args = parser.parse_args()
    bootstrap_report_file = Path(args.bootstrap_report_file).resolve() if args.bootstrap_report_file else None

    manager = AgentCliManager()
    manager.ensure_layout()

    if args.check_auth:
        _write_auth_status(manager, Path(args.status_file).resolve() if args.status_file else None)
        return 0

    if args.ensure:
        report_payload = _ensure_with_diagnostics(manager)
        _write_bootstrap_report(bootstrap_report_file, report_payload)
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
