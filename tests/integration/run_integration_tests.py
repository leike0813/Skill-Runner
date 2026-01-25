import asyncio
import sys
import os
import yaml  # type: ignore[import-untyped]
import json
import io
import zipfile
import time
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

# Add project root to path
# tests/integration/run_integration_tests.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

# Set env
enforced_data_dir = False
if "UV_CACHE_DIR" not in os.environ:
    os.environ["UV_CACHE_DIR"] = str(PROJECT_ROOT / "data" / "uv_cache")
if "SKILL_RUNNER_DATA_DIR" not in os.environ:
    os.environ["SKILL_RUNNER_DATA_DIR"] = "/home/joshua/Workspace/Code/Skill-Runner/data"
    enforced_data_dir = True

from server.models import RunCreateRequest, RunStatus
from server.services.workspace_manager import workspace_manager
from server.services.job_orchestrator import job_orchestrator
from server.services.skill_registry import skill_registry
from server.services.schema_validator import schema_validator
from server.services.options_policy import options_policy
from server.services.model_registry import model_registry
from server.services.cache_key_builder import (
    compute_skill_fingerprint,
    compute_input_manifest_hash,
    compute_cache_key
)
from server.services.run_store import run_store
import uuid

TEST_ROOT = PROJECT_ROOT / "tests"
SUITES_DIR = TEST_ROOT / "suites"
FIXTURES_DIR = TEST_ROOT / "fixtures"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Colors.OKCYAN,
        logging.INFO: Colors.OKGREEN,
        logging.WARNING: Colors.WARNING,
        logging.ERROR: Colors.FAIL,
        logging.CRITICAL: Colors.FAIL,
    }

    def format(self, record):
        message = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno, Colors.ENDC)
        return f"{color}{message}{Colors.ENDC}"

def setup_logging():
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
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    color_formatter = ColorFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
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

async def run_test_case(skill_id: str, case: Dict, default_engine: str = "gemini", verbose: int = 0, no_cache: bool = False):
    logger.info("Running Case: %s", case["name"])
    logger.info("  Description: %s", case.get("description", ""))

    # 1. Create Request
    engine = case.get("engine", default_engine)
    model = None
    try:
        catalog = model_registry.get_models(engine, refresh=True)
        if catalog.models:
            entry = catalog.models[0]
            if engine == "codex" and entry.supported_effort:
                model = f"{entry.id}@{entry.supported_effort[0]}"
            else:
                model = entry.id
    except Exception:
        logger.warning("Failed to load model catalog for engine %s", engine)

    req = RunCreateRequest(
        skill_id=skill_id,
        engine=engine,
        parameter=case.get("parameters", {}),
        model=model,
        runtime_options={"verbose": verbose, "no_cache": no_cache}
    )
    runtime_opts = options_policy.validate_runtime_options(req.runtime_options)
    engine_opts = {}
    if req.model:
        validated = model_registry.validate_model(req.engine, req.model)
        engine_opts["model"] = validated["model"]
        if "model_reasoning_effort" in validated:
            engine_opts["model_reasoning_effort"] = validated["model_reasoning_effort"]

    request_id = str(uuid.uuid4())
    request_payload = req.model_dump()
    request_payload["engine_options"] = engine_opts
    request_payload["runtime_options"] = runtime_opts
    workspace_manager.create_request(request_id, request_payload)
    run_store.create_request(
        request_id=request_id,
        skill_id=req.skill_id,
        engine=req.engine,
        parameter=req.parameter,
        engine_options=engine_opts,
        runtime_options=runtime_opts
    )

    run_id = None
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        logger.error("Skill %s not found", skill_id)
        return False
    engine_allowed = bool(skill.engines) and engine in skill.engines
    if not engine_allowed:
        try:
            workspace_manager.create_run(req)
        except ValueError:
            logger.info("  [Pass] Engine mismatch rejected by workspace_manager.")
            return True
        logger.error("  [Fail] Engine mismatch was not rejected by workspace_manager.")
        return False

    has_input_schema = bool(skill.schemas and "input" in skill.schemas)

    # 2. Upload Files
    input_map = case.get("inputs", {})
    if input_map:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, filename in input_map.items():
                fixture_path = FIXTURES_DIR / filename
                if not fixture_path.exists():
                     logger.error("  [Error] Fixture not found: %s", filename)
                     return False
                zf.writestr(key, fixture_path.read_bytes())
        
        workspace_manager.handle_upload(request_id, zip_buffer.getvalue())
        logger.info("  [Upload] Uploaded %s files", len(input_map))

    # 3. Cache check + Execute
    if input_map or has_input_schema:
        manifest_path = workspace_manager.write_input_manifest(request_id)
        manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
        skill_fingerprint = compute_skill_fingerprint(skill, req.engine)
        cache_key = compute_cache_key(
            skill_id=req.skill_id,
            engine=req.engine,
            skill_fingerprint=skill_fingerprint,
            parameter=req.parameter,
            engine_options=engine_opts,
            input_manifest_hash=manifest_hash
        )
        run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        if not no_cache:
            cached_run = run_store.get_cached_run(cache_key)
            if cached_run:
                run_id = cached_run
                logger.info("  [Cache] Hit: %s", run_id)
        if run_id is None:
            run_status = workspace_manager.create_run(req)
            run_id = run_status.run_id
            workspace_manager.promote_request_uploads(request_id, run_id)
            run_store.create_run(run_id, cache_key, RunStatus.QUEUED)
            merged_options = {**engine_opts, **runtime_opts}
            logger.info("  [Exec] Starting Job...")
            await job_orchestrator.run_job(
                run_id=run_id,
                skill_id=req.skill_id,
                engine_name=req.engine,
                options=merged_options,
                cache_key=cache_key
            )
    else:
        manifest_path = workspace_manager.write_input_manifest(request_id)
        manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
        skill_fingerprint = compute_skill_fingerprint(skill, req.engine)
        cache_key = compute_cache_key(
            skill_id=req.skill_id,
            engine=req.engine,
            skill_fingerprint=skill_fingerprint,
            parameter=req.parameter,
            engine_options=engine_opts,
            input_manifest_hash=manifest_hash
        )
        run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        if not no_cache:
            cached_run = run_store.get_cached_run(cache_key)
            if cached_run:
                run_id = cached_run
                logger.info("  [Cache] Hit: %s", run_id)
        if run_id is None:
            run_status = workspace_manager.create_run(req)
            run_id = run_status.run_id
            run_store.create_run(run_id, cache_key, RunStatus.QUEUED)
            merged_options = {**engine_opts, **runtime_opts}
            logger.info("  [Exec] Starting Job...")
            await job_orchestrator.run_job(
                run_id=run_id,
                skill_id=req.skill_id,
                engine_name=req.engine,
                options=merged_options,
                cache_key=cache_key
            )

    if not run_id:
        logger.error("Failed to produce run_id")
        return False

    # 4. Validate (Wait for status with Polling)
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        logger.error("Run dir not found for %s", run_id)
        return False
    status_file = run_dir / "status.json"
    
    final_status = None
    start_time = time.time()
    timeout_seconds = 600  # 10 minutes wait time for heavy skills

    while time.time() - start_time < timeout_seconds:
        if status_file.exists():
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                    final_status = status_data.get("status")
                
                if final_status in ["succeeded", "failed"]:
                    break
            except Exception:
                pass # Retry on read error (race condition)
        
        await asyncio.sleep(2)
        logger.info("  [Wait] Waiting for completion... Status: %s", final_status)

    # Determine final outcome
    if final_status not in ["succeeded", "failed"]:
         logger.error(
             "  [Timeout] Job timed out after %ss. Last status: %s",
             timeout_seconds,
             final_status
         )
         return False

    expectations = case.get("expectations", {})
    expected_status = expectations.get("status")
    
    success = True
    
    # Check Status
    if expected_status and expected_status != "any":
        expected_set = expected_status if isinstance(expected_status, list) else [expected_status]
        if final_status not in expected_set:
            logger.error(
                "  [Fail] Status Mismatch. Expected %s, Got %s",
                expected_status,
                final_status
            )
            success = False
        else:
            logger.info("  [Pass] Status: %s", final_status)
    else:
        logger.info("  [Info] Status: %s", final_status)

    # Check Artifacts (run_dir/artifacts)
    for artifact in expectations.get("artifacts_present", []):
        path = run_dir / "artifacts" / artifact
        if not path.exists():
            logger.error("  [Fail] Missing Artifact: %s", artifact)
            success = False
        else:
            logger.info("  [Pass] Artifact Found: %s", artifact)

    # Check Output JSON
    expected_json = expectations.get("output_json", {})
    if expected_json:
        result_path = run_dir / "result" / "result.json"
        if result_path.exists():
            with open(result_path, 'r') as f:
                actual_result = json.load(f)
            
            check_data = actual_result
            if "data" in actual_result and isinstance(actual_result["data"], dict):
                check_data = actual_result["data"]

            for k, v in expected_json.items():
                if k not in check_data:
                     logger.error("  [Fail] Result JSON missing key: %s", k)
                     success = False
                elif check_data[k] != v:
                     logger.error(
                         "  [Fail] Result JSON mismatch for %s. Expected %s, Got %s",
                         k,
                         v,
                         check_data[k]
                     )
                     success = False
                else:
                     logger.info("  [Pass] Result JSON Key: %s", k)
        else:
             logger.error("  [Fail] Result JSON file missing")
             success = False

    if not success:
        stdout = (run_dir / "logs" / "stdout.txt")
        stderr = (run_dir / "logs" / "stderr.txt")
        logger.warning("  --- STDOUT ---")
        if stdout.exists():
            logger.warning(stdout.read_text())
        logger.warning("  --- STDERR ---")
        if stderr.exists():
            logger.warning(stderr.read_text())

    return success

async def main():
    logger.debug("Runner Loaded")
    parser = argparse.ArgumentParser(description="Skill Runner Integration Test Runner")
    parser.add_argument("-k", "--keyword", help="Filter test suites by keyword (e.g. skill id)", default="")
    parser.add_argument("-e", "--engine", help="Override execution engine (e.g. codex, gemini)", default=None)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output (-v: stdout, -vv: stdout+stderr)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage for this run")
    args = parser.parse_args()

    skill_registry.scan_skills()
    
    results = []
    
    suites = list(SUITES_DIR.glob("*.yaml"))
    
    if args.keyword:
        suites = [s for s in suites if args.keyword in s.name]
        
    if not suites:
        logger.error("No suites found matching '%s'", args.keyword)
        sys.exit(5)

    logger.info("Collecting %s test suites...", len(suites))

    for suite_file in suites:
        try:
            with open(suite_file, 'r') as f:
                suite = yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to load suite %s", suite_file)
            continue
            
        skill_id = suite.get("skill_id")
        if not skill_id:
             logger.error("Suite %s missing 'skill_id'", suite_file.name)
             continue
             
        suite_engine = args.engine if args.engine else suite.get("engine", "gemini")

        logger.info("=== Suite: %s (Engine: %s) ===", skill_id, suite_engine)
        
        cases = suite.get("cases", [])
        if not cases:
             logger.warning("No cases found in suite %s.", suite_file.name)

        for case in cases:
            res = await run_test_case(
                skill_id,
                case,
                default_engine=suite_engine,
                verbose=args.verbose,
                no_cache=args.no_cache
            )
            results.append(res)
            
    total = len(results)
    passed = sum(results)
    
    logger.info("=== Summary ===")
    logger.info("Total: %s, Passed: %s, Failed: %s", total, passed, total - passed)
    
    if passed != total:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    setup_logging()
    if enforced_data_dir:
        logger.info(
            "Enforced SKILL_RUNNER_DATA_DIR = %s",
            os.environ["SKILL_RUNNER_DATA_DIR"]
        )
    asyncio.run(main())
