import asyncio
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from ..models import RunStatus, SkillManifest
from ..services.workspace_manager import workspace_manager
from ..services.skill_registry import skill_registry
from ..adapters.codex_adapter import CodexAdapter
from ..adapters.gemini_adapter import GeminiAdapter
from ..adapters.iflow_adapter import IFlowAdapter
from ..services.schema_validator import schema_validator
from ..services.run_store import run_store
from ..services.concurrency_manager import concurrency_manager
from ..config import config

class JobOrchestrator:
    """
    Manages the background execution of skills.
    
    Responsibilities:
    - Coordinates lifecycle of a run (QUEUED -> RUNNING -> SUCCEEDED/FAILED).
    - Resolves the correct EngineAdapter based on the request.
    - Validates inputs before execution.
    - Captures results and normalizes outputs.
    - Writes status updates to the workspace.
    """
    def __init__(self):
        # In v0, we just map engines to class instances
        self.adapters = {
            "codex": CodexAdapter(),
            "gemini": GeminiAdapter(),
            "iflow": IFlowAdapter(),
        }

    async def run_job(
        self,
        run_id: str,
        skill_id: str,
        engine_name: str,
        options: Dict[str, Any],
        cache_key: Optional[str] = None,
        skill_override: Optional[SkillManifest] = None,
        temp_request_id: Optional[str] = None,
    ):
        """
        Background task to execute the skill.
        
        Args:
            run_id: Unique UUID of the run.
            skill_id: ID of the skill to execute.
            engine_name: 'codex' or 'gemini'.
            options: Execution options (e.g. verbose flag, model config).
            
        Side Effects:
            - Updates 'status.json' in run_dir.
            - Writes 'logs/stdout.txt', 'logs/stderr.txt'.
            - Writes 'result/result.json'.
        """
        slot_acquired = False
        run_dir: Path | None = None
        await concurrency_manager.acquire_slot()
        slot_acquired = True
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            logger.error("Run dir %s not found", run_id)
            return
        final_status: Optional[RunStatus] = None
        normalized_error_message: Optional[str] = None

        # 1. Update status to RUNNING
        self._update_status(run_dir, RunStatus.RUNNING)
        self._update_latest_run_id(run_id)

        try:
            # 2. Get Skill
            skill = skill_override or skill_registry.get_skill(skill_id)
            if not skill:
                raise ValueError(f"Skill {skill_id} not found during execution")
            if not skill.schemas or not all(key in skill.schemas for key in ("input", "parameter", "output")):
                raise ValueError("Schema missing: input/parameter/output must be defined")

            # 3. Get Adapter
            adapter = self.adapters.get(engine_name)
            if not adapter:
                raise ValueError(f"Engine {engine_name} not supported")

            # 4. Load Input
            with open(run_dir / "input.json", 'r') as input_file:
                input_data = json.load(input_file)

            # 4.1 Validate Input
            # Support both legacy "input" and new "files"/"parameters" schemas
            # The input.json contains the full request (including skill_id, etc.)
            # 4.1 Validate Input & Parameters
            # The input.json now contains "parameter" dict
            real_params = input_data.get("parameter", {})
            input_errors = []
            
            # 1. Validate 'parameter' (Values)
            if skill.schemas and "parameter" in skill.schemas:
                 # Validator expects the data to match the schema
                 # strict validation of the parameter payload
                 input_errors.extend(schema_validator.validate_schema(skill, real_params, "parameter"))

            # 2. Validate 'input' (Files) - Existence Check ONLY
            if skill.schemas and "input" in skill.schemas:
                 # We don't check JSON payload for files anymore.
                 # We check if the required files exist in uploads/
                 run_uploads_dir = run_dir / "uploads"
                 input_keys = schema_validator.get_schema_keys(skill, "input")
                 required_keys = schema_validator.get_schema_required(skill, "input")
                 
                 # We only check 'required' fields if we had access to required list, 
                 # but schema_validator.validate_schema usually does structure check.
                 # Here we just check existence for now as a pre-flight, 
                 # OR we let the adapter explode.
                 # Better to Validate here:
                 # BUT schema_validator.validate_schema expects a JSON dict.
                 # We can construct a "virtual" input dict based on existing files to validate against schema.
                 
                 virtual_file_input = {}
                 existing_files = set()
                 if run_uploads_dir.exists():
                     for upload_path in run_uploads_dir.iterdir():
                         if upload_path.name in input_keys:
                             virtual_file_input[upload_path.name] = str(upload_path.absolute())
                             existing_files.add(upload_path.name)
                 
                 missing_required = [key for key in required_keys if key not in existing_files]
                 if missing_required:
                     input_errors.append(f"Missing required input files: {', '.join(missing_required)}")
                 
                 # Validate this virtual dict against the input schema
                 # This ensures required fields (files) are present
                 input_errors.extend(schema_validator.validate_schema(skill, virtual_file_input, "input"))

            if input_errors:
                raise ValueError(f"Input validation failed: {str(input_errors)}")
            
            # 5. Execute
            result = await adapter.run(skill, input_data, run_dir, options)

            # 6. Verify Result and Normalize
            warnings: list[str] = []
            output_data = {}
            output_errors: list[str] = []
            if result.exit_code == 0:
                if result.output_file_path and result.output_file_path.exists():
                    try:
                        with open(result.output_file_path, "r") as f:
                            output_data = json.load(f)
                        output_errors = schema_validator.validate_output(skill, output_data)
                    except Exception as e:
                        output_errors = [f"Failed to validate output schema: {str(e)}"]
                        output_data = {}
                else:
                    output_errors = ["Output JSON missing or unreadable"]

            # 6.1 Normalization (N0)
            # Create standard envelope
            artifacts_dir = run_dir / "artifacts"
            artifacts = []
            if artifacts_dir.exists():
                for path in artifacts_dir.rglob("*"):
                    if path.is_file():
                        artifacts.append(path.relative_to(run_dir).as_posix())
            artifacts.sort()
            required_artifacts = [
                artifact.pattern
                for artifact in skill.artifacts
                if artifact.required
            ] if skill.artifacts else []
            missing_artifacts = []
            for pattern in required_artifacts:
                expected_path = f"artifacts/{pattern}"
                if expected_path not in artifacts:
                    missing_artifacts.append(pattern)
            if missing_artifacts:
                output_errors.append(
                    f"Missing required artifacts: {', '.join(missing_artifacts)}"
                )
            has_output_error = bool(output_errors)
            normalized_status = "success" if result.exit_code == 0 and not has_output_error else "failed"
            normalized_error: dict[str, Any] | None = None
            if normalized_status != "success":
                normalized_error = {
                    "message": "; ".join(output_errors) if has_output_error else f"Exit code {result.exit_code}",
                    "stderr": result.raw_stderr
                }
            normalized_result = {
                "status": normalized_status,
                "data": output_data if normalized_status == "success" else None,
                "artifacts": artifacts,
                "validation_warnings": warnings,
                "error": normalized_error
            }
            
            # Allow adapter to communicate error via output if present
            if result.exit_code != 0 and result.raw_stderr:
                 pass # already handled in error
                 
            # Overwrite result.json with normalized version
            # Ensure parent dir exists (it should)
            result_path = run_dir / "result" / "result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w") as f:
                json.dump(normalized_result, f, indent=2)

            # 7. Finalize status and bundles
            final_status = RunStatus.SUCCEEDED if normalized_status == "success" else RunStatus.FAILED
            normalized_error_message = normalized_error["message"] if normalized_error else None
            self._build_run_bundle(run_dir, debug=False)
            self._build_run_bundle(run_dir, debug=True)
            self._update_status(run_dir, final_status, error=normalized_error, warnings=warnings)
            run_store.update_run_status(run_id, final_status, str(result_path))
            if cache_key and final_status == RunStatus.SUCCEEDED:
                run_store.record_cache_entry(cache_key, run_id)

        except Exception as e:
            logger.exception("Job failed")
            final_status = RunStatus.FAILED
            normalized_error_message = str(e)
            if run_dir:
                self._update_status(run_dir, RunStatus.FAILED, error={"message": str(e)})
            run_store.update_run_status(run_id, RunStatus.FAILED)
        finally:
            if temp_request_id and final_status:
                try:
                    from .temp_skill_run_manager import temp_skill_run_manager
                    temp_skill_run_manager.on_terminal(
                        temp_request_id,
                        final_status,
                        error=normalized_error_message,
                        debug_keep_temp=bool(options.get("debug_keep_temp")),
                    )
                except Exception:
                    logger.warning(
                        "Failed to finalize temporary-skill lifecycle for request %s",
                        temp_request_id,
                        exc_info=True,
                    )
            if slot_acquired:
                await concurrency_manager.release_slot()

    def _update_status(self, run_dir: Path, status: RunStatus, error: Optional[Dict] = None, warnings: Optional[List[str]] = None):
        # In v0, we might just rely on checking result/ but let's write a status file
        # This mirrors what WorkspaceManager does but updates it
        # Ideally WorkspaceManager should own this writing logic
        # For simplicity, I'll write a simple status.json sidecar
        
        warnings_list = warnings or []
        status_data = {
            "status": status,
            "updated_at": str(datetime.now()),
            "error": error,
            "warnings": warnings_list
        }
        with open(run_dir / "status.json", "w") as f:
            json.dump(status_data, f)

    def _update_latest_run_id(self, run_id: str):
        """Updates the latest_run_id file in the runs directory."""
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        try:
            with open(runs_dir / "latest_run_id", "w") as f:
                f.write(run_id)
        except Exception as e:
            logger.exception("Failed to update latest_run_id")

    def _build_run_bundle(self, run_dir: Path, debug: bool) -> str:
        bundle_dir = run_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_filename = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        bundle_path = bundle_dir / bundle_filename
        manifest_filename = "manifest_debug.json" if debug else "manifest.json"
        manifest_path = bundle_dir / manifest_filename

        entries = []
        bundle_candidates = self._bundle_candidates(run_dir, debug, bundle_path, manifest_path)
        for path in bundle_candidates:
            if not path.is_file():
                continue
            rel_path = path.relative_to(run_dir).as_posix()
            entries.append({
                "path": rel_path,
                "size": path.stat().st_size,
                "sha256": self._hash_file(path)
            })

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"files": entries}, f, indent=2)

        if bundle_path.exists():
            bundle_path.unlink()

        import zipfile
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in bundle_candidates:
                if not path.is_file():
                    continue
                rel_path = path.relative_to(run_dir).as_posix()
                zf.write(path, rel_path)
            zf.write(manifest_path, manifest_path.relative_to(run_dir).as_posix())

        return bundle_path.relative_to(run_dir).as_posix()

    def _bundle_candidates(self, run_dir: Path, debug: bool, bundle_path: Path, manifest_path: Path) -> list[Path]:
        if debug:
            candidates = [path for path in run_dir.rglob("*") if path.is_file()]
        else:
            candidates = []
            result_path = run_dir / "result" / "result.json"
            if result_path.exists():
                candidates.append(result_path)
            artifacts_dir = run_dir / "artifacts"
            if artifacts_dir.exists():
                candidates.extend([path for path in artifacts_dir.rglob("*") if path.is_file()])

        bundle_dir = run_dir / "bundle"
        candidates = [
            path for path in candidates
            if path != bundle_path and path != manifest_path and path.parent != bundle_dir
        ]
        return candidates

    def _hash_file(self, path: Path) -> str:
        import hashlib

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

job_orchestrator = JobOrchestrator()

# Helper imports for inside async method
import json
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)
