from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _build_pytest_args(keyword: str, passthrough: list[str]) -> list[str]:
    args = ["-m", "pytest", "tests/engine_integration"]
    if keyword:
        args.extend(["-k", keyword])
    args.extend(passthrough)
    return args


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Skill Runner engine integration pytest runner"
    )
    parser.add_argument(
        "-k",
        "--keyword",
        help="Forwarded to pytest -k to filter golden engine integration cases",
        default="",
    )
    parser.add_argument(
        "-e",
        "--engine",
        help="Filter captured golden fixtures by engine name",
        default=None,
    )
    args, passthrough = parser.parse_known_args()

    env = os.environ.copy()
    if isinstance(args.engine, str) and args.engine.strip():
        env["SKILL_RUNNER_ENGINE_INTEGRATION_ENGINE_FILTER"] = args.engine.strip()

    command = [sys.executable, *_build_pytest_args(args.keyword, passthrough)]
    print("Executing:", " ".join(command))
    return subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
