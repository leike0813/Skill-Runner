from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .config import resolve_harness_config
from .errors import HarnessError
from .runtime import HarnessLaunchRequest, HarnessResumeRequest, HarnessRuntime


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-harness",
        description="External runtime harness for Skill Runner engines",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start a harness attempt")
    start.add_argument("--run-dir", dest="run_selector", help="Run selector to reuse run folder")
    start.add_argument(
        "--auto",
        dest="auto_mode",
        action="store_true",
        help="Run in auto mode (default is interactive mode)",
    )
    start.add_argument(
        "--translate",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="Translate output level",
    )
    start.add_argument("engine", help="Engine name")
    start.add_argument(
        "passthrough_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to engine command",
    )

    resume = subparsers.add_parser("resume", help="Resume from interactive handle")
    resume.add_argument(
        "--translate",
        type=int,
        default=None,
        choices=[0, 1, 2, 3],
        help="Override translate output level",
    )
    resume.add_argument("handle", help="Handle suffix")
    resume.add_argument("message", nargs=argparse.REMAINDER, help="Reply message")
    return parser


def _build_direct_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-harness",
        description="External runtime harness for Skill Runner engines",
    )
    parser.add_argument("--run-dir", dest="run_selector", help="Run selector to reuse run folder")
    parser.add_argument(
        "--auto",
        dest="auto_mode",
        action="store_true",
        help="Run in auto mode (default is interactive mode)",
    )
    parser.add_argument(
        "--translate",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="Translate output level",
    )
    parser.add_argument("engine", help="Engine name")
    parser.add_argument(
        "passthrough_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to engine command",
    )
    return parser


def _normalize_passthrough(args: list[str]) -> list[str]:
    if not args:
        return []
    if args[0] == "--":
        return args[1:]
    return args


def _run(argv: Sequence[str]) -> dict:
    argv_list = list(argv)
    runtime = HarnessRuntime(resolve_harness_config())

    if argv_list and argv_list[0] in {"start", "resume"}:
        parsed = _build_legacy_parser().parse_args(argv_list)
        if parsed.command == "start":
            start_request = HarnessLaunchRequest(
                engine=parsed.engine,
                passthrough_args=_normalize_passthrough(list(parsed.passthrough_args)),
                translate_level=int(parsed.translate),
                run_selector=parsed.run_selector,
                execution_mode="auto" if bool(parsed.auto_mode) else "interactive",
            )
            return runtime.start(start_request)

        if parsed.command == "resume":
            message = " ".join(parsed.message).strip()
            resume_request = HarnessResumeRequest(
                handle=parsed.handle,
                message=message,
                translate_level=parsed.translate,
            )
            return runtime.resume(resume_request)
        raise HarnessError("INVALID_COMMAND", "Unsupported command")

    parsed = _build_direct_parser().parse_args(argv_list)
    start_request = HarnessLaunchRequest(
        engine=parsed.engine,
        passthrough_args=_normalize_passthrough(list(parsed.passthrough_args)),
        translate_level=int(parsed.translate),
        run_selector=parsed.run_selector,
        execution_mode="auto" if bool(parsed.auto_mode) else "interactive",
    )
    return runtime.start(start_request)


def _print_success(payload: dict) -> None:
    run_id = payload.get("run_id")
    run_dir = payload.get("run_dir")
    handle = payload.get("handle")
    session_id = payload.get("session_id")
    exit_code = payload.get("exit_code")
    operation = payload.get("_operation", "start")

    print(f"Run id: {run_id}")
    print(f"Run directory: {run_dir}")
    print(f"Run handle: {handle if isinstance(handle, str) and handle else 'unknown'}")
    if isinstance(session_id, str) and session_id:
        print(f"Session: session_id={session_id}")
    else:
        print("Session: not detected")
    print(f"{str(operation).capitalize()} complete. exitCode={exit_code}")


def main(argv: Sequence[str] | None = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    try:
        payload = _run(argv_list)
        if argv_list and argv_list[0] == "resume":
            payload["_operation"] = "resume"
        else:
            payload["_operation"] = "start"
        _print_success(payload)
        return 0
    except HarnessError as exc:
        print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
