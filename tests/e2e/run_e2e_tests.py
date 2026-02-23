import argparse
import asyncio
import io
import logging
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml  # type: ignore[import-untyped]
from fastapi.testclient import TestClient  # type: ignore[import-not-found]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from server.main import app
from server.services.model_registry import model_registry
from server.services.skill_registry import skill_registry
from tests.common.skill_fixture_loader import (
    build_fixture_skill_zip,
    fixture_skill_engines,
    fixture_skill_needs_input,
)

SUITES_DIR = PROJECT_ROOT / "tests" / "engine_integration" / "suites"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

DEFAULT_DATA_DIR = "/home/joshua/Workspace/Code/Skill-Runner/data"

logger = logging.getLogger("e2e")


def _setup_logging(verbose: int) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def _ensure_cli_available(engine: str) -> None:
    cmd = {"codex": "codex", "gemini": "gemini", "iflow": "iflow"}[engine]
    result = subprocess.run([cmd, "--version"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd} not available (exit {result.returncode})")


def _load_suites(keyword: str) -> Iterable[Dict[str, Any]]:
    suites = list(SUITES_DIR.glob("*.yaml"))
    if keyword:
        suites = [s for s in suites if keyword in s.name]
    if not suites:
        raise RuntimeError(f"No suites found matching '{keyword}'")
    for suite_path in suites:
        with open(suite_path, "r", encoding="utf-8") as f:
            suite = yaml.safe_load(f)
        suite["__path__"] = suite_path
        yield suite


def _build_zip(inputs: Dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, filename in inputs.items():
            fixture_path = FIXTURES_DIR / filename
            if not fixture_path.exists():
                raise RuntimeError(f"Fixture not found: {filename}")
            zf.writestr(key, fixture_path.read_bytes())
    buffer.seek(0)
    return buffer.read()


def _pick_model(engine: str) -> str:
    catalog = model_registry.get_models(engine, refresh=True)
    if not catalog.models:
        raise RuntimeError(f"No models available for engine {engine}")
    entry = catalog.models[0]
    if engine == "codex" and entry.supported_effort:
        return f"{entry.id}@{entry.supported_effort[0]}"
    return entry.id


def _wait_for_status(
    client: TestClient,
    request_id: str,
    timeout_sec: int = 120,
    endpoint_prefix: str = "/v1/jobs",
    interactive_replies: list[Any] | None = None,
) -> Dict[str, Any]:
    replies = list(interactive_replies or [])
    reply_index = 0
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        res = client.get(f"{endpoint_prefix}/{request_id}")
        if res.status_code != 200:
            raise RuntimeError(f"Status check failed: {res.status_code}")
        payload = res.json()
        if payload["status"] in ("succeeded", "failed", "canceled"):
            return payload
        if payload["status"] == "waiting_user":
            if reply_index >= len(replies):
                raise RuntimeError(
                    "Request entered waiting_user but no interactive_replies remain in case config"
                )
            pending_res = client.get(f"{endpoint_prefix}/{request_id}/interaction/pending")
            if pending_res.status_code != 200:
                raise RuntimeError(f"Pending check failed: {pending_res.status_code}")
            pending = pending_res.json().get("pending")
            if not isinstance(pending, dict):
                raise RuntimeError("waiting_user without pending interaction payload")

            step = replies[reply_index]
            reply_index += 1
            if isinstance(step, dict):
                response_payload = step.get("response")
                idempotency_key = step.get("idempotency_key")
            else:
                response_payload = step
                idempotency_key = None
            if response_payload is None:
                raise RuntimeError("interactive_replies entry must provide response payload")

            reply_body: dict[str, Any] = {
                "interaction_id": pending["interaction_id"],
                "response": response_payload,
            }
            if isinstance(idempotency_key, str) and idempotency_key:
                reply_body["idempotency_key"] = idempotency_key
            reply_res = client.post(
                f"{endpoint_prefix}/{request_id}/interaction/reply",
                json=reply_body,
            )
            if reply_res.status_code != 200:
                raise RuntimeError(f"Reply failed: {reply_res.status_code} {reply_res.text}")
            continue
        time.sleep(1)
    raise RuntimeError(f"Request {request_id} did not finish within {timeout_sec}s")


def _assert_json_matches(expected: Dict[str, Any], actual: Dict[str, Any]) -> None:
    for key, value in expected.items():
        if key not in actual:
            raise AssertionError(f"Missing key: {key}")
        if isinstance(value, dict):
            if not isinstance(actual[key], dict):
                raise AssertionError(f"Expected dict for key: {key}")
            _assert_json_matches(value, actual[key])
        else:
            if actual[key] != value:
                raise AssertionError(f"Mismatch for {key}: expected {value}, got {actual[key]}")


async def run_suite_case(
    client: TestClient,
    engine: str,
    skill_id: str,
    case: Dict[str, Any],
    verbose: int,
    no_cache: bool,
    debug: bool,
    skill_source: str = "installed",
    skill_fixture: str | None = None,
) -> bool:
    name = case.get("name", "unnamed")
    inputs = case.get("inputs", {})
    parameters = case.get("parameters", {})
    expectations = case.get("expectations", {})
    interactive_replies = case.get("interactive_replies")
    fixture_id = skill_fixture or skill_id

    if skill_source == "temp":
        engines = fixture_skill_engines(PROJECT_ROOT, fixture_id)
        engine_allowed = bool(engines) and engine in engines
        needs_upload = bool(inputs) or fixture_skill_needs_input(PROJECT_ROOT, fixture_id)
    else:
        skill = skill_registry.get_skill(skill_id)
        if not skill:
            raise RuntimeError(f"Skill not found: {skill_id}")
        engine_allowed = bool(skill.engines) and engine in skill.engines
        needs_upload = bool(inputs) or bool(skill.schemas and "input" in skill.schemas)

    model = _pick_model(engine)
    if skill_source == "temp":
        create_payload = {
            "engine": engine,
            "parameter": parameters,
            "model": model,
            "runtime_options": {"no_cache": True, "verbose": verbose, "debug": debug},
        }
        logger.info("Case: %s (source=temp, engine=%s, debug=%s)", name, engine, debug)
        logger.info("Create payload: %s", create_payload)
        create_res = client.post("/v1/temp-skill-runs", json=create_payload)
        if create_res.status_code != 200:
            raise RuntimeError(f"Create temp run failed for {name}: {create_res.status_code}")
        create_body = create_res.json()
        request_id = create_body["request_id"]
        logger.info("Create response: request_id=%s", request_id)

        skill_zip = build_fixture_skill_zip(PROJECT_ROOT, fixture_id)
        if not inputs:
            logger.info("No inputs provided; uploading empty zip to trigger input validation.")
        input_zip = _build_zip(inputs)
        upload_res = client.post(
            f"/v1/temp-skill-runs/{request_id}/upload",
            files={
                "skill_package": (f"{fixture_id}.zip", skill_zip, "application/zip"),
                "file": ("inputs.zip", input_zip, "application/zip"),
            },
        )
        if not engine_allowed:
            if upload_res.status_code == 400:
                logger.info("Engine mismatch rejected as expected.")
                return True
            raise AssertionError(
                f"{name} expected engine mismatch failure but got {upload_res.status_code}"
            )
        if upload_res.status_code != 200:
            raise RuntimeError(f"Upload failed for {name}: {upload_res.status_code}")
        upload_body = upload_res.json()
        logger.info("Upload response: extracted=%s", upload_body.get("extracted_files"))
        status_payload = _wait_for_status(
            client,
            request_id,
            endpoint_prefix="/v1/temp-skill-runs",
            interactive_replies=interactive_replies,
        )
        result_path = f"/v1/temp-skill-runs/{request_id}/result"
        artifacts_path = f"/v1/temp-skill-runs/{request_id}/artifacts"
        bundle_path = f"/v1/temp-skill-runs/{request_id}/bundle"
    else:
        create_payload = {
            "skill_id": skill_id,
            "engine": engine,
            "parameter": parameters,
            "model": model,
            "runtime_options": {"no_cache": no_cache, "verbose": verbose, "debug": debug},
        }
        logger.info("Case: %s (source=installed, engine=%s, no_cache=%s, debug=%s)", name, engine, no_cache, debug)
        logger.info("Create payload: %s", create_payload)
        create_res = client.post("/v1/jobs", json=create_payload)
        if not engine_allowed:
            if create_res.status_code == 400:
                logger.info("Engine mismatch rejected as expected.")
                return True
            raise AssertionError(
                f"{name} expected engine mismatch failure but got {create_res.status_code}"
            )
        if create_res.status_code != 200:
            raise RuntimeError(f"Create run failed for {name}: {create_res.status_code}")

        create_body = create_res.json()
        request_id = create_body["request_id"]
        logger.info("Create response: request_id=%s cache_hit=%s", request_id, create_body.get("cache_hit"))

        if needs_upload:
            if not inputs:
                logger.info("No inputs provided; uploading empty zip to trigger input validation.")
            zip_bytes = _build_zip(inputs)
            upload_res = client.post(
                f"/v1/jobs/{request_id}/upload",
                files={"file": ("inputs.zip", zip_bytes, "application/zip")}
            )
            if upload_res.status_code != 200:
                raise RuntimeError(f"Upload failed for {name}: {upload_res.status_code}")
            upload_body = upload_res.json()
            logger.info(
                "Upload response: cache_hit=%s extracted=%s",
                upload_body.get("cache_hit"),
                upload_body.get("extracted_files"),
            )

        status_payload = _wait_for_status(
            client,
            request_id,
            interactive_replies=interactive_replies,
        )
        result_path = f"/v1/jobs/{request_id}/result"
        artifacts_path = f"/v1/jobs/{request_id}/artifacts"
        bundle_path = f"/v1/jobs/{request_id}/bundle"

    logger.info("Final status: %s", status_payload["status"])
    expected_status = expectations.get("status")
    if expected_status and expected_status != "any":
        expected_set = expected_status if isinstance(expected_status, list) else [expected_status]
        if status_payload["status"] not in expected_set:
            raise AssertionError(f"{name} status mismatch: {status_payload['status']} != {expected_status}")

    result_res = client.get(result_path)
    result_body = None
    if result_res.status_code == 404 and status_payload["status"] in ("failed", "canceled"):
        logger.info("Result not available for failed run; skipping result assertions.")
    elif result_res.status_code != 200:
        raise RuntimeError(f"Result fetch failed for {name}: {result_res.status_code}")
    else:
        result_body = result_res.json()
        logger.info("Result response: %s", result_body)

    expected_output = expectations.get("output_json")
    if expected_output is not None and result_body is not None:
        _assert_json_matches(expected_output, result_body["result"]["data"])

    artifacts_res = client.get(artifacts_path)
    if artifacts_res.status_code != 200:
        raise RuntimeError(f"Artifacts fetch failed for {name}: {artifacts_res.status_code}")
    artifacts_body = artifacts_res.json()
    logger.info("Artifacts response: %s", artifacts_body)

    download_res = client.get(bundle_path)
    if download_res.status_code != 200 or not download_res.content:
        raise AssertionError(f"{name} bundle download failed")

    bundle_name = "run_bundle_debug.zip" if debug else "run_bundle.zip"
    downloads_dir = Path(os.environ.get("SKILL_RUNNER_DATA_DIR", DEFAULT_DATA_DIR)) / "e2e_downloads" / request_id
    downloads_dir.mkdir(parents=True, exist_ok=True)
    bundle_file = downloads_dir / bundle_name
    bundle_file.write_bytes(download_res.content)
    logger.info("Bundle saved to: %s", bundle_file)

    expected_artifacts = expectations.get("artifacts_present", [])
    if expected_artifacts:
        with zipfile.ZipFile(io.BytesIO(download_res.content), "r") as zf:
            entries = set(zf.namelist())
        for artifact in expected_artifacts:
            artifact_path = artifact if "/" in artifact else f"artifacts/{artifact}"
            if artifact_path not in entries:
                raise AssertionError(f"{name} missing artifact in bundle {artifact_path}")

    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Skill Runner REST E2E Test Runner")
    parser.add_argument("-k", "--keyword", help="Filter test suites by keyword", default="")
    parser.add_argument("-c", "--case", help="Filter test cases by name", default="")
    parser.add_argument("-e", "--engine", help="Override execution engine (codex/gemini/iflow)", default=None)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output (-v, -vv)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage")
    parser.add_argument("--debug", action="store_true", help="Enable debug bundle (include full run dir)")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    if "SKILL_RUNNER_DATA_DIR" not in os.environ:
        os.environ["SKILL_RUNNER_DATA_DIR"] = DEFAULT_DATA_DIR
        logger.info("Enforced SKILL_RUNNER_DATA_DIR=%s", DEFAULT_DATA_DIR)

    engine_override = args.engine
    if engine_override:
        _ensure_cli_available(engine_override)

    skill_registry.scan_skills()
    client = TestClient(app)

    results = []
    for suite in _load_suites(args.keyword):
        skill_id = suite.get("skill_id")
        cases = suite.get("cases", [])
        if not skill_id:
            continue
        skill_source = str(suite.get("skill_source", "installed")).strip().lower()
        skill_fixture = suite.get("skill_fixture")

        suite_engine = engine_override or suite.get("engine", "gemini")
        _ensure_cli_available(suite_engine)

        for case in cases:
            if args.case and args.case not in case.get("name", ""):
                continue
            success = await run_suite_case(
                client,
                suite_engine,
                skill_id,
                case,
                verbose=args.verbose,
                no_cache=args.no_cache,
                debug=args.debug,
                skill_source=skill_source,
                skill_fixture=skill_fixture,
            )
            results.append(success)

    total = len(results)
    passed = sum(1 for item in results if item)
    if total == 0:
        print("No matching cases executed.")
        return 5
    print(f"Total: {total}, Passed: {passed}, Failed: {total - passed}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
