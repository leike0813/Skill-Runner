import asyncio
import io
import json
import logging
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict

from server.models import RunCreateRequest, RunStatus
from server.services.cache_key_builder import (
    compute_cache_key,
    compute_input_manifest_hash,
    compute_skill_fingerprint,
)
from server.services.job_orchestrator import job_orchestrator
from server.services.model_registry import model_registry
from server.services.options_policy import options_policy
from server.services.run_store import run_store
from server.services.skill_registry import skill_registry
from server.services.temp_skill_run_manager import temp_skill_run_manager
from server.services.temp_skill_run_store import temp_skill_run_store
from server.services.workspace_manager import workspace_manager
from tests.common.skill_fixture_loader import (
    build_fixture_skill_zip,
    fixture_skill_engines,
)

logger = logging.getLogger(__name__)


class EngineIntegrationHarnessFixture:
    def __init__(self, project_root: Path, fixtures_dir: Path) -> None:
        self.project_root = project_root
        self.fixtures_dir = fixtures_dir

    def _build_input_zip(self, input_map: Dict[str, str]) -> bytes:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, filename in input_map.items():
                fixture_path = self.fixtures_dir / filename
                if not fixture_path.exists():
                    raise FileNotFoundError(filename)
                zf.writestr(key, fixture_path.read_bytes())
        return zip_buffer.getvalue()

    async def run_test_case(
        self,
        skill_id: str,
        case: Dict[str, Any],
        default_engine: str = "gemini",
        verbose: int = 0,
        no_cache: bool = False,
        skill_source: str = "installed",
        skill_fixture: str | None = None,
    ) -> bool:
        logger.info("Running Case: %s", case["name"])
        logger.info("  Description: %s", case.get("description", ""))

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

        effective_no_cache = no_cache
        req = RunCreateRequest(
            skill_id=skill_id,
            engine=engine,
            parameter=case.get("parameters", {}),
            model=model,
            runtime_options={"verbose": verbose, "no_cache": effective_no_cache},
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
        input_map = case.get("inputs", {})
        run_id = None

        if skill_source == "temp":
            fixture_id = skill_fixture or skill_id
            fixture_engines = fixture_skill_engines(self.project_root, fixture_id)
            engine_allowed = bool(fixture_engines) and engine in fixture_engines

            temp_skill_run_store.create_request(
                request_id=request_id,
                engine=req.engine,
                parameter=req.parameter,
                model=req.model,
                engine_options=engine_opts,
                runtime_options=runtime_opts,
            )
            skill_package_bytes = build_fixture_skill_zip(self.project_root, fixture_id)
            skill = temp_skill_run_manager.stage_skill_package(request_id, skill_package_bytes)
            req.skill_id = skill.id

            if not engine_allowed:
                try:
                    workspace_manager.create_run_for_skill(req, skill)
                except ValueError:
                    logger.info("  [Pass] Engine mismatch rejected by workspace_manager.")
                    return True
                logger.error("  [Fail] Engine mismatch was not rejected by workspace_manager.")
                return False

            if input_map:
                try:
                    workspace_manager.handle_upload(request_id, self._build_input_zip(input_map))
                except FileNotFoundError as exc:
                    logger.error("  [Error] Fixture not found: %s", str(exc))
                    return False
                logger.info("  [Upload] Uploaded %s files", len(input_map))

            run_status = workspace_manager.create_run_for_skill(req, skill)
            run_id = run_status.run_id
            workspace_manager.promote_request_uploads(request_id, run_id)
            merged_options = {**engine_opts, **runtime_opts}
            logger.info("  [Exec] Starting Job (temp skill)...")
            await job_orchestrator.run_job(
                run_id=run_id,
                skill_id=req.skill_id,
                engine_name=req.engine,
                options=merged_options,
                cache_key=None,
                skill_override=skill,
                temp_request_id=request_id,
            )
        else:
            run_store.create_request(
                request_id=request_id,
                skill_id=req.skill_id,
                engine=req.engine,
                parameter=req.parameter,
                engine_options=engine_opts,
                runtime_options=runtime_opts,
            )
            installed_skill = skill_registry.get_skill(skill_id)
            if not installed_skill:
                logger.error("Skill %s not found", skill_id)
                return False
            engine_allowed = bool(installed_skill.engines) and engine in installed_skill.engines
            if not engine_allowed:
                try:
                    workspace_manager.create_run(req)
                except ValueError:
                    logger.info("  [Pass] Engine mismatch rejected by workspace_manager.")
                    return True
                logger.error("  [Fail] Engine mismatch was not rejected by workspace_manager.")
                return False

            has_input_schema = bool(installed_skill.schemas and "input" in installed_skill.schemas)
            if input_map:
                try:
                    workspace_manager.handle_upload(request_id, self._build_input_zip(input_map))
                except FileNotFoundError as exc:
                    logger.error("  [Error] Fixture not found: %s", str(exc))
                    return False
                logger.info("  [Upload] Uploaded %s files", len(input_map))

            manifest_path = workspace_manager.write_input_manifest(request_id)
            manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
            skill_fingerprint = compute_skill_fingerprint(installed_skill, req.engine)
            cache_key = compute_cache_key(
                skill_id=req.skill_id,
                engine=req.engine,
                skill_fingerprint=skill_fingerprint,
                parameter=req.parameter,
                engine_options=engine_opts,
                input_manifest_hash=manifest_hash,
            )
            run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
            run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
            if not effective_no_cache:
                cached_run = run_store.get_cached_run(cache_key)
                if cached_run:
                    run_id = cached_run
                    logger.info("  [Cache] Hit: %s", run_id)
            if run_id is None:
                run_status = workspace_manager.create_run(req)
                run_id = run_status.run_id
                if input_map or has_input_schema:
                    workspace_manager.promote_request_uploads(request_id, run_id)
                run_store.create_run(run_id, cache_key, RunStatus.QUEUED)
                merged_options = {**engine_opts, **runtime_opts}
                logger.info("  [Exec] Starting Job...")
                await job_orchestrator.run_job(
                    run_id=run_id,
                    skill_id=req.skill_id,
                    engine_name=req.engine,
                    options=merged_options,
                    cache_key=cache_key,
                )

        if not run_id:
            logger.error("Failed to produce run_id")
            return False

        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            logger.error("Run dir not found for %s", run_id)
            return False
        status_file = run_dir / "status.json"

        final_status = None
        start_time = time.time()
        timeout_seconds = 600

        while time.time() - start_time < timeout_seconds:
            if status_file.exists():
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                        final_status = status_data.get("status")
                    if final_status in ["succeeded", "failed"]:
                        break
                except Exception:
                    pass
            await asyncio.sleep(2)
            logger.info("  [Wait] Waiting for completion... Status: %s", final_status)

        if final_status not in ["succeeded", "failed"]:
            logger.error(
                "  [Timeout] Job timed out after %ss. Last status: %s",
                timeout_seconds,
                final_status,
            )
            return False

        expectations = case.get("expectations", {})
        expected_status = expectations.get("status")

        success = True
        if expected_status and expected_status != "any":
            expected_set = expected_status if isinstance(expected_status, list) else [expected_status]
            if final_status not in expected_set:
                logger.error(
                    "  [Fail] Status Mismatch. Expected %s, Got %s",
                    expected_status,
                    final_status,
                )
                success = False
            else:
                logger.info("  [Pass] Status: %s", final_status)
        else:
            logger.info("  [Info] Status: %s", final_status)

        for artifact in expectations.get("artifacts_present", []):
            path = run_dir / "artifacts" / artifact
            if not path.exists():
                logger.error("  [Fail] Missing Artifact: %s", artifact)
                success = False
            else:
                logger.info("  [Pass] Artifact Found: %s", artifact)

        expected_json = expectations.get("output_json", {})
        if expected_json:
            result_path = run_dir / "result" / "result.json"
            if result_path.exists():
                with open(result_path, "r", encoding="utf-8") as f:
                    actual_result = json.load(f)

                check_data = actual_result
                if "data" in actual_result and isinstance(actual_result["data"], dict):
                    check_data = actual_result["data"]

                for key, value in expected_json.items():
                    if key not in check_data:
                        logger.error("  [Fail] Result JSON missing key: %s", key)
                        success = False
                    elif check_data[key] != value:
                        logger.error(
                            "  [Fail] Result JSON mismatch for %s. Expected %s, Got %s",
                            key,
                            value,
                            check_data[key],
                        )
                        success = False
                    else:
                        logger.info("  [Pass] Result JSON Key: %s", key)
            else:
                logger.error("  [Fail] Result JSON file missing")
                success = False

        if not success:
            stdout = run_dir / "logs" / "stdout.txt"
            stderr = run_dir / "logs" / "stderr.txt"
            logger.warning("  --- STDOUT ---")
            if stdout.exists():
                logger.warning(stdout.read_text(encoding="utf-8"))
            logger.warning("  --- STDERR ---")
            if stderr.exists():
                logger.warning(stderr.read_text(encoding="utf-8"))

        if skill_source == "temp":
            temp_skill_run_manager.cleanup_temp_assets(request_id)

        return success
