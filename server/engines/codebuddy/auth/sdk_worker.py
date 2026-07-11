from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


async def _authenticate(args: argparse.Namespace) -> int:
    # Intentionally imported only in the isolated worker process.
    from codebuddy_agent_sdk import authenticate

    auth_flow = await authenticate(
        environment=args.environment,
        codebuddy_code_path=args.codebuddy_path,
        env={},
        timeout=args.timeout,
    )
    _emit({"type": "auth_url", "auth_url": str(auth_flow.auth_url or "")})
    result = await auth_flow.wait(timeout=args.timeout)
    userinfo = result.userinfo
    token = str(userinfo.token or "")
    user_id = str(userinfo.user_id or "")
    if not token or not user_id:
        raise RuntimeError("CodeBuddy SDK returned incomplete credential")
    _emit(
        {
            "type": "credential",
            "token": token,
            "user_id": user_id,
        }
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--environment", choices=("internal", "public"), required=True)
    parser.add_argument("--codebuddy-path", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--temp-root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    temp_root = Path(args.temp_root).resolve()
    if not temp_root.is_dir():
        _emit({"type": "error", "error": "CodeBuddy auth temporary root is unavailable"})
        return 2
    expected_config = temp_root / "config"
    if Path(os.environ.get("CODEBUDDY_CONFIG_DIR", "")).resolve() != expected_config.resolve():
        _emit({"type": "error", "error": "CodeBuddy auth worker environment is invalid"})
        return 2
    try:
        return asyncio.run(_authenticate(args))
    except (OSError, RuntimeError, ValueError, TypeError, asyncio.TimeoutError) as exc:
        _emit({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
