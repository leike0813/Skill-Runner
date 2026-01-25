import argparse
import io
import json
import logging
import os
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

import httpx
import yaml  # type: ignore[import-untyped]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SUITES_DIR = PROJECT_ROOT / "tests" / "suites"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

DEFAULT_DOWNLOAD_DIR = "/home/joshua/Workspace/Code/Skill-Runner/e2e-test-download"

logger = logging.getLogger("e2e")


def _setup_logging(verbose: int) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


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


def _load_skill_manifest(skill_id: str) -> Dict[str, Any]:
    manifest_path = PROJECT_ROOT / "skills" / skill_id / "assets" / "runner.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Skill manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _skill_engines(skill_id: str) -> List[str]:
    manifest = _load_skill_manifest(skill_id)
    engines = manifest.get("engines")
    if engines is None:
        engines = manifest.get("engine")
    if engines is None:
        return []
    if isinstance(engines, str):
        return [engines]
    return list(engines)


def _skill_needs_input(skill_id: str) -> bool:
    schema_path = PROJECT_ROOT / "skills" / skill_id / "assets" / "input.schema.json"
    return schema_path.exists()


def _pick_model(client: httpx.Client, base_url: str, engine: str) -> str:
    res = client.get(f"{base_url}/v1/engines/{engine}/models")
    if res.status_code != 200:
        raise RuntimeError(f"Model list failed for {engine}: {res.status_code}")
    catalog = res.json()
    models = catalog.get("models", [])
    if not models:
        raise RuntimeError(f"No models available for engine {engine}")
    entry = models[0]
    if engine == "codex" and entry.get("supported_effort"):
        return f"{entry['id']}@{entry['supported_effort'][0]}"
    return entry["id"]


def _wait_for_status(
    client: httpx.Client,
    base_url: str,
    request_id: str,
    timeout_sec: int = 600
) -> Dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        res = client.get(f"{base_url}/v1/jobs/{request_id}")
        if res.status_code != 200:
            raise RuntimeError(f"Status check failed: {res.status_code}")
        payload = res.json()
        if payload["status"] in ("succeeded", "failed", "canceled"):
            return payload
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


def run_suite_case(
    client: httpx.Client,
    base_url: str,
    engine: str,
    skill_id: str,
    case: Dict[str, Any],
    verbose: int,
    no_cache: bool,
    debug: bool
) -> bool:
    name = case.get("name", "unnamed")
    inputs = case.get("inputs", {})
    parameters = case.get("parameters", {})
    expectations = case.get("expectations", {})

    engines = _skill_engines(skill_id)
    engine_allowed = bool(engines) and engine in engines

    model = _pick_model(client, base_url, engine)
    create_payload = {
        "skill_id": skill_id,
        "engine": engine,
        "parameter": parameters,
        "model": model,
        "runtime_options": {"no_cache": no_cache, "verbose": verbose, "debug": debug}
    }
    logger.info("Case: %s (engine=%s, no_cache=%s, debug=%s)", name, engine, no_cache, debug)
    logger.info("Create payload: %s", create_payload)
    create_res = client.post(f"{base_url}/v1/jobs", json=create_payload)
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

    needs_upload = bool(inputs)
    if not inputs:
        needs_upload = _skill_needs_input(skill_id)

    if needs_upload:
        if not inputs:
            logger.info("No inputs provided; uploading empty zip to trigger input validation.")
        zip_bytes = _build_zip(inputs)
        upload_res = client.post(
            f"{base_url}/v1/jobs/{request_id}/upload",
            files={"file": ("inputs.zip", zip_bytes, "application/zip")}
        )
        if upload_res.status_code != 200:
            raise RuntimeError(f"Upload failed for {name}: {upload_res.status_code}")

        upload_body = upload_res.json()
        logger.info("Upload response: cache_hit=%s extracted=%s", upload_body.get("cache_hit"), upload_body.get("extracted_files"))

    status_payload = _wait_for_status(client, base_url, request_id)
    logger.info("Final status: %s", status_payload["status"])
    expected_status = expectations.get("status")
    if expected_status and expected_status != "any":
        expected_set = expected_status if isinstance(expected_status, list) else [expected_status]
        if status_payload["status"] not in expected_set:
            raise AssertionError(f"{name} status mismatch: {status_payload['status']} != {expected_status}")

    result_res = client.get(f"{base_url}/v1/jobs/{request_id}/result")
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

    artifacts_res = client.get(f"{base_url}/v1/jobs/{request_id}/artifacts")
    if artifacts_res.status_code != 200:
        raise RuntimeError(f"Artifacts fetch failed for {name}: {artifacts_res.status_code}")
    artifacts_body = artifacts_res.json()
    logger.info("Artifacts response: %s", artifacts_body)

    download_res = client.get(f"{base_url}/v1/jobs/{request_id}/bundle")
    if download_res.status_code != 200 or not download_res.content:
        raise AssertionError(f"{name} bundle download failed")

    bundle_name = "run_bundle_debug.zip" if debug else "run_bundle.zip"
    downloads_dir = Path(os.environ.get("E2E_DOWNLOAD_DIR", DEFAULT_DOWNLOAD_DIR)) / request_id
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill Runner REST E2E Test Runner (Container)")
    parser.add_argument("-k", "--keyword", help="Filter test suites by keyword", default="")
    parser.add_argument("-c", "--case", help="Filter test cases by name", default="")
    parser.add_argument("-e", "--engine", help="Override execution engine (codex/gemini/iflow)", default=None)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbose output (-v, -vv)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage")
    parser.add_argument("--debug", action="store_true", help="Enable debug bundle (include full run dir)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Target service base URL")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    if "E2E_DOWNLOAD_DIR" not in os.environ:
        os.environ["E2E_DOWNLOAD_DIR"] = DEFAULT_DOWNLOAD_DIR
        logger.info("Enforced E2E_DOWNLOAD_DIR=%s", DEFAULT_DOWNLOAD_DIR)

    base_url = args.base_url.rstrip("/")
    client = httpx.Client(timeout=120.0)

    results = []
    for suite in _load_suites(args.keyword):
        skill_id = suite.get("skill_id")
        cases = suite.get("cases", [])
        if not skill_id:
            continue

        suite_engine = args.engine or suite.get("engine", "gemini")

        for case in cases:
            if args.case and args.case not in case.get("name", ""):
                continue
            success = run_suite_case(
                client,
                base_url,
                suite_engine,
                skill_id,
                case,
                verbose=args.verbose,
                no_cache=args.no_cache,
                debug=args.debug
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
    raise SystemExit(main())
