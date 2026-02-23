import argparse
import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml  # type: ignore[import-untyped]

# tests/engine_integration/run_engine_integration_tests.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from server.services.skill_registry import skill_registry
from tests.engine_integration.harness_fixture import EngineIntegrationHarnessFixture

TEST_ROOT = PROJECT_ROOT / "tests"
SUITES_DIR = TEST_ROOT / "engine_integration" / "suites"
FIXTURES_DIR = TEST_ROOT / "fixtures"


class _Colors:
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


class _ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: _Colors.OKCYAN,
        logging.INFO: _Colors.OKGREEN,
        logging.WARNING: _Colors.WARNING,
        logging.ERROR: _Colors.FAIL,
        logging.CRITICAL: _Colors.FAIL,
    }

    def format(self, record):
        message = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno, _Colors.ENDC)
        return f"{color}{message}{_Colors.ENDC}"


def setup_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    data_dir = Path(os.environ["SKILL_RUNNER_DATA_DIR"])
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = Path(os.environ.get("LOG_FILE", str(logs_dir / "run_tests.log")))
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    color_formatter = _ColorFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(color_formatter)

    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


logger = logging.getLogger(__name__)


def _ensure_runner_env() -> bool:
    enforced_data_dir = False
    if "UV_CACHE_DIR" not in os.environ:
        os.environ["UV_CACHE_DIR"] = str(PROJECT_ROOT / "data" / "uv_cache")
    if "SKILL_RUNNER_DATA_DIR" not in os.environ:
        os.environ["SKILL_RUNNER_DATA_DIR"] = str(PROJECT_ROOT / "data")
        enforced_data_dir = True
    return enforced_data_dir


async def main() -> int:
    parser = argparse.ArgumentParser(description="Skill Runner Engine Integration Test Runner")
    parser.add_argument("-k", "--keyword", help="Filter suites by keyword", default="")
    parser.add_argument("-e", "--engine", help="Override execution engine", default=None)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbose output (-v: stdout, -vv: stdout+stderr)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage")
    args = parser.parse_args()

    skill_registry.scan_skills()
    harness = EngineIntegrationHarnessFixture(project_root=PROJECT_ROOT, fixtures_dir=FIXTURES_DIR)

    suites = list(SUITES_DIR.glob("*.yaml"))
    if args.keyword:
        suites = [s for s in suites if args.keyword in s.name]
    if not suites:
        logger.error("No suites found matching '%s'", args.keyword)
        return 5

    logger.info("Collecting %s engine integration suites...", len(suites))
    results: list[bool] = []

    for suite_file in suites:
        try:
            with open(suite_file, "r", encoding="utf-8") as f:
                suite = yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to load suite %s", suite_file)
            continue

        skill_id = suite.get("skill_id")
        if not skill_id:
            logger.error("Suite %s missing 'skill_id'", suite_file.name)
            continue
        skill_source = str(suite.get("skill_source", "installed")).strip().lower()
        skill_fixture = suite.get("skill_fixture")
        suite_engine = args.engine if args.engine else suite.get("engine", "gemini")

        logger.info(
            "=== Suite: %s (Engine: %s, Source: %s) ===",
            skill_id,
            suite_engine,
            skill_source,
        )

        cases = suite.get("cases", [])
        if not cases:
            logger.warning("No cases found in suite %s", suite_file.name)

        for case in cases:
            result = await harness.run_test_case(
                skill_id,
                case,
                default_engine=suite_engine,
                verbose=args.verbose,
                no_cache=args.no_cache,
                skill_source=skill_source,
                skill_fixture=skill_fixture,
            )
            results.append(result)

    total = len(results)
    passed = sum(results)
    logger.info("=== Summary ===")
    logger.info("Total: %s, Passed: %s, Failed: %s", total, passed, total - passed)
    return 0 if passed == total else 1


if __name__ == "__main__":
    enforced_data_dir = _ensure_runner_env()
    setup_logging()
    if enforced_data_dir:
        logger.info("Enforced SKILL_RUNNER_DATA_DIR = %s", os.environ["SKILL_RUNNER_DATA_DIR"])
    raise SystemExit(asyncio.run(main()))
