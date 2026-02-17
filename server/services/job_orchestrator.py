import asyncio
import contextlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from ..models import (
    EngineSessionHandle,
    EngineInteractiveProfile,
    EngineInteractiveProfileKind,
    ExecutionMode,
    InteractiveErrorCode,
    RunStatus,
    SkillManifest,
)
from ..services.agent_cli_manager import AgentCliManager
from ..services.workspace_manager import workspace_manager
from ..services.skill_registry import skill_registry
from ..adapters.codex_adapter import CodexAdapter
from ..adapters.gemini_adapter import GeminiAdapter
from ..adapters.iflow_adapter import IFlowAdapter
from ..services.schema_validator import schema_validator
from ..services.run_store import run_store
from ..services.concurrency_manager import concurrency_manager
from ..services.run_folder_trust_manager import run_folder_trust_manager
from ..services.session_timeout import resolve_session_timeout
from ..config import config


class RunCanceled(Exception):
    """Raised when run is canceled by user request."""


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
        self.agent_cli_manager = AgentCliManager()
        self._sticky_watchdog_tasks: dict[str, asyncio.Task[None]] = {}
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
        release_slot_on_exit = True
        sticky_slot_held = bool(options.get("__sticky_slot_held"))
        run_dir: Path | None = None
        if sticky_slot_held:
            slot_acquired = True
        else:
            await concurrency_manager.acquire_slot()
            slot_acquired = True
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            logger.error("Run dir %s not found", run_id)
            return
        request_record = run_store.get_request_by_run_id(run_id)
        request_id = request_record.get("request_id") if request_record else None
        execution_mode = str(
            options.get(
                "execution_mode",
                (request_record or {}).get("runtime_options", {}).get(
                    "execution_mode", ExecutionMode.AUTO.value
                ),
            )
        )
        is_interactive = execution_mode == ExecutionMode.INTERACTIVE.value
        interactive_require_user_reply = self._resolve_interactive_require_user_reply(
            options=options,
            request_record=request_record or {},
        )
        interactive_profile: Optional[EngineInteractiveProfile] = None
        if is_interactive and request_id:
            interactive_profile = self._resolve_interactive_profile(
                request_id=request_id,
                engine_name=engine_name,
                options=options,
            )
        if run_store.is_cancel_requested(run_id):
            canceled_error = self._build_canceled_error()
            result_path = self._write_canceled_result(run_dir, canceled_error)
            self._update_status(
                run_dir,
                RunStatus.CANCELED,
                error=canceled_error,
                effective_session_timeout_sec=(
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                ),
            )
            run_store.update_run_status(
                run_id,
                RunStatus.CANCELED,
                str(result_path) if result_path is not None else None,
            )
            if temp_request_id:
                with contextlib.suppress(Exception):
                    from .temp_skill_run_store import temp_skill_run_store

                    temp_skill_run_store.update_status(
                        temp_request_id,
                        RunStatus.CANCELED,
                        error=canceled_error["message"],
                    )
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()
            return
        final_status: Optional[RunStatus] = None
        normalized_error_message: Optional[str] = None
        trust_registered = False

        # 1. Update status to RUNNING
        self._update_status(
            run_dir,
            RunStatus.RUNNING,
            effective_session_timeout_sec=(
                interactive_profile.session_timeout_sec if interactive_profile is not None else None
            ),
        )
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

            # 4.1 Validate Input & Parameters
            real_params = input_data.get("parameter", {})
            input_errors = []
            
            # 1. Validate 'parameter' (Values)
            if skill.schemas and "parameter" in skill.schemas:
                 # Validator expects the data to match the schema
                 # strict validation of the parameter payload
                 input_errors.extend(schema_validator.validate_schema(skill, real_params, "parameter"))

            # 2. Validate mixed 'input' (file + inline)
            if skill.schemas and "input" in skill.schemas:
                 input_errors.extend(
                     schema_validator.validate_input_for_execution(skill, run_dir, input_data)
                 )

            if input_errors:
                raise ValueError(f"Input validation failed: {str(input_errors)}")

            if run_store.is_cancel_requested(run_id):
                raise RunCanceled()

            run_folder_trust_manager.register_run_folder(engine_name, run_dir)
            trust_registered = True
            run_options = dict(options)
            run_options["__run_id"] = run_id
            if is_interactive and request_id and interactive_profile:
                run_options["__interactive_profile"] = interactive_profile.model_dump(mode="json")
                self._inject_interactive_resume_context(
                    request_id=request_id,
                    profile=interactive_profile,
                    options=run_options,
                    run_dir=run_dir,
                )

            # 5. Execute
            try:
                result = await adapter.run(skill, input_data, run_dir, run_options)
            finally:
                if trust_registered:
                    try:
                        run_folder_trust_manager.remove_run_folder(engine_name, run_dir)
                    except Exception:
                        logger.warning(
                            "Failed to cleanup run folder trust for engine=%s run_id=%s",
                            engine_name,
                            run_id,
                            exc_info=True,
                        )
                    trust_registered = False
            if run_store.is_cancel_requested(run_id):
                raise RunCanceled()

            # 6. Verify Result and Normalize
            warnings: list[str] = []
            output_data = {}
            output_errors: list[str] = []
            pending_interaction: Optional[Dict[str, Any]] = None
            repair_level = result.repair_level or "none"
            if result.exit_code == 0:
                if result.output_file_path and result.output_file_path.exists():
                    try:
                        with open(result.output_file_path, "r") as f:
                            output_data = json.load(f)
                        if is_interactive:
                            pending_interaction = self._extract_pending_interaction(output_data)
                        if pending_interaction is None and is_interactive and self._looks_like_ask_user_payload(output_data):
                            output_errors = ["Invalid ask_user payload"]
                        elif pending_interaction is None:
                            output_errors = schema_validator.validate_output(skill, output_data)
                            if not output_errors and repair_level == "deterministic_generic":
                                warnings.append("OUTPUT_REPAIRED_GENERIC")
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
            forced_failure_reason = result.failure_reason if result.failure_reason in {
                "AUTH_REQUIRED",
                "TIMEOUT",
                InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
                InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
            } else None
            if pending_interaction and is_interactive and request_id and interactive_profile:
                wait_status = self._persist_waiting_interaction(
                    adapter=adapter,
                    run_id=run_id,
                    run_dir=run_dir,
                    request_id=request_id,
                    profile=interactive_profile,
                    interactive_require_user_reply=interactive_require_user_reply,
                    pending_interaction=pending_interaction,
                    raw_stdout=result.raw_stdout,
                )
                if wait_status is not None:
                    forced_failure_reason = wait_status

            normalized_status = "success"
            if forced_failure_reason or result.exit_code != 0 or has_output_error:
                normalized_status = "failed"
            if pending_interaction and not forced_failure_reason and not has_output_error:
                normalized_status = RunStatus.WAITING_USER.value
            normalized_error: dict[str, Any] | None = None
            if normalized_status == RunStatus.WAITING_USER.value:
                normalized_error = None
            elif normalized_status != "success":
                error_code: Optional[str] = None
                if forced_failure_reason == "AUTH_REQUIRED":
                    error_code = "AUTH_REQUIRED"
                    error_message = "AUTH_REQUIRED: engine authentication is required or expired"
                elif forced_failure_reason == "TIMEOUT":
                    error_code = "TIMEOUT"
                    effective_timeout = self._resolve_hard_timeout_seconds(options)
                    error_message = (
                        f"TIMEOUT: engine execution exceeded hard timeout "
                        f"({effective_timeout}s)"
                    )
                elif forced_failure_reason in {
                    InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                    InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
                    InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                }:
                    error_code = forced_failure_reason
                    error_message = forced_failure_reason
                elif has_output_error:
                    error_message = "; ".join(output_errors)
                else:
                    error_message = f"Exit code {result.exit_code}"
                normalized_error = {
                    "code": error_code,
                    "message": error_message,
                    "stderr": result.raw_stderr,
                }
            normalized_result = {
                "status": normalized_status,
                "data": output_data if normalized_status == "success" else None,
                "artifacts": artifacts,
                "repair_level": repair_level,
                "validation_warnings": warnings,
                "error": normalized_error,
                "pending_interaction": pending_interaction,
                "interactive_profile": (
                    interactive_profile.model_dump(mode="json")
                    if interactive_profile is not None
                    else None
                ),
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
            if normalized_status == "success":
                final_status = RunStatus.SUCCEEDED
            elif normalized_status == RunStatus.WAITING_USER.value:
                final_status = RunStatus.WAITING_USER
            else:
                final_status = RunStatus.FAILED
            normalized_error_message = normalized_error["message"] if normalized_error else None
            if (
                final_status == RunStatus.WAITING_USER
                and interactive_profile is not None
                and request_id
                and pending_interaction
            ):
                wait_runtime = run_store.get_sticky_wait_runtime(request_id)
                if wait_runtime and wait_runtime.get("wait_deadline_at"):
                    if interactive_profile.kind == EngineInteractiveProfileKind.STICKY_PROCESS:
                        release_slot_on_exit = False
                    self._schedule_sticky_watchdog(
                        request_id=request_id,
                        run_id=run_id,
                        wait_deadline_at=str(wait_runtime["wait_deadline_at"]),
                    )
                elif interactive_profile.kind == EngineInteractiveProfileKind.STICKY_PROCESS:
                    release_slot_on_exit = False
            elif request_id:
                self.cancel_sticky_watchdog(request_id)
            if final_status != RunStatus.WAITING_USER:
                self._build_run_bundle(run_dir, debug=False)
                self._build_run_bundle(run_dir, debug=True)
            self._update_status(
                run_dir,
                final_status,
                error=normalized_error,
                warnings=warnings,
                effective_session_timeout_sec=(
                    interactive_profile.session_timeout_sec if interactive_profile is not None else None
                ),
            )
            run_store.update_run_status(run_id, final_status, str(result_path))
            if cache_key and final_status == RunStatus.SUCCEEDED:
                run_store.record_cache_entry(cache_key, run_id)

        except RunCanceled:
            final_status = RunStatus.CANCELED
            canceled_error = self._build_canceled_error()
            normalized_error_message = canceled_error["message"]
            if request_id:
                self.cancel_sticky_watchdog(request_id)
            result_path = self._write_canceled_result(run_dir, canceled_error) if run_dir else None
            if run_dir:
                self._update_status(
                    run_dir,
                    RunStatus.CANCELED,
                    error=canceled_error,
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                )
            run_store.update_run_status(
                run_id,
                RunStatus.CANCELED,
                str(result_path) if result_path is not None else None,
            )
        except Exception as e:
            logger.exception("Job failed")
            final_status = RunStatus.FAILED
            if request_id:
                self.cancel_sticky_watchdog(request_id)
            normalized_error = self._error_from_exception(e)
            normalized_error_message = str(normalized_error.get("message", str(e)))
            if run_dir:
                self._update_status(
                    run_dir,
                    RunStatus.FAILED,
                    error=normalized_error,
                    effective_session_timeout_sec=(
                        interactive_profile.session_timeout_sec if interactive_profile is not None else None
                    ),
                )
            run_store.update_run_status(run_id, RunStatus.FAILED)
        finally:
            if trust_registered and run_dir:
                try:
                    run_folder_trust_manager.remove_run_folder(engine_name, run_dir)
                except Exception:
                    logger.warning(
                        "Failed to cleanup run folder trust in finalizer for engine=%s run_id=%s",
                        engine_name,
                        run_id,
                        exc_info=True,
                    )
            if temp_request_id and final_status in {
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
                RunStatus.CANCELED,
            }:
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
            if slot_acquired and release_slot_on_exit:
                await concurrency_manager.release_slot()

    async def cancel_run(
        self,
        *,
        run_id: str,
        engine_name: str,
        run_dir: Path,
        status: RunStatus,
        request_id: Optional[str] = None,
        temp_request_id: Optional[str] = None,
    ) -> bool:
        changed = run_store.set_cancel_requested(run_id, True)
        if status == RunStatus.RUNNING:
            adapter = self.adapters.get(engine_name)
            if adapter is not None:
                with contextlib.suppress(Exception):
                    await adapter.cancel_run_process(run_id)

        canceled_error = self._build_canceled_error()
        self._write_canceled_result(run_dir, canceled_error)
        self._update_status(
            run_dir,
            RunStatus.CANCELED,
            error=canceled_error,
            effective_session_timeout_sec=(
                run_store.get_effective_session_timeout(request_id) if request_id else None
            ),
        )
        run_store.update_run_status(run_id, RunStatus.CANCELED)

        if request_id:
            self.cancel_sticky_watchdog(request_id)
            if status == RunStatus.WAITING_USER:
                profile = run_store.get_interactive_profile(request_id) or {}
                if profile.get("kind") == EngineInteractiveProfileKind.STICKY_PROCESS.value:
                    await concurrency_manager.release_slot()

        if temp_request_id:
            from .temp_skill_run_store import temp_skill_run_store

            temp_skill_run_store.update_status(
                temp_request_id,
                RunStatus.CANCELED,
                error=canceled_error["message"],
            )
        return changed

    def _build_canceled_error(self) -> Dict[str, Any]:
        return {
            "code": "CANCELED_BY_USER",
            "message": "Canceled by user request",
        }

    def _write_canceled_result(self, run_dir: Optional[Path], error: Dict[str, Any]) -> Optional[Path]:
        if run_dir is None:
            return None
        result_payload: Dict[str, Any] = {
            "status": RunStatus.CANCELED.value,
            "data": None,
            "artifacts": [],
            "repair_level": "none",
            "validation_warnings": [],
            "error": error,
            "pending_interaction": None,
            "interactive_profile": None,
        }
        result_path = run_dir / "result" / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result_path

    def _update_status(
        self,
        run_dir: Path,
        status: RunStatus,
        error: Optional[Dict] = None,
        warnings: Optional[List[str]] = None,
        effective_session_timeout_sec: Optional[int] = None,
    ):
        # In v0, we might just rely on checking result/ but let's write a status file
        # This mirrors what WorkspaceManager does but updates it
        # Ideally WorkspaceManager should own this writing logic
        # For simplicity, I'll write a simple status.json sidecar
        
        warnings_list = warnings or []
        status_data = {
            "status": status,
            "updated_at": str(datetime.now()),
            "error": error,
            "warnings": warnings_list,
            "effective_session_timeout_sec": effective_session_timeout_sec,
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

    def _resolve_hard_timeout_seconds(self, options: Dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except Exception:
            pass
        return default_timeout

    def _resolve_session_timeout_seconds(self, options: Dict[str, Any]) -> int:
        return resolve_session_timeout(
            options,
            default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
        ).value

    def _resolve_interactive_require_user_reply(
        self,
        *,
        options: Dict[str, Any],
        request_record: Dict[str, Any],
    ) -> bool:
        if "interactive_require_user_reply" in options:
            value = options.get("interactive_require_user_reply")
            if isinstance(value, bool):
                return value
        runtime_options = request_record.get("runtime_options", {})
        value = runtime_options.get("interactive_require_user_reply", True)
        return bool(value)

    def _resolve_interactive_profile(
        self,
        request_id: str,
        engine_name: str,
        options: Dict[str, Any],
    ) -> EngineInteractiveProfile:
        existing = run_store.get_interactive_profile(request_id)
        if existing:
            profile = EngineInteractiveProfile.model_validate(existing)
            if run_store.get_effective_session_timeout(request_id) is None:
                run_store.set_effective_session_timeout(request_id, profile.session_timeout_sec)
            return profile
        session_timeout_sec = self._resolve_session_timeout_seconds(options)
        profile = self.agent_cli_manager.resolve_interactive_profile(
            engine=engine_name,
            session_timeout_sec=session_timeout_sec,
        )
        run_store.set_effective_session_timeout(request_id, session_timeout_sec)
        run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        return profile

    def _inject_interactive_resume_context(
        self,
        request_id: str,
        profile: EngineInteractiveProfile,
        options: Dict[str, Any],
        run_dir: Path,
    ) -> None:
        if "__interactive_reply_payload" not in options:
            return
        interaction_id_raw = options.get("__interactive_reply_interaction_id", 0)
        try:
            interaction_id = int(interaction_id_raw)
        except Exception:
            interaction_id = 0
        if interaction_id > 0:
            resolution_mode_raw = options.get("__interactive_resolution_mode", "user_reply")
            resolution_mode = (
                str(resolution_mode_raw).strip() if resolution_mode_raw else "user_reply"
            )
            run_store.append_interaction_history(
                request_id=request_id,
                interaction_id=interaction_id,
                event_type="reply",
                payload={
                    "response": options.get("__interactive_reply_payload"),
                    "resolution_mode": resolution_mode,
                    "resolved_at": datetime.utcnow().isoformat(),
                    "auto_decide_reason": options.get("__interactive_auto_reason"),
                    "auto_decide_policy": options.get("__interactive_auto_policy"),
                },
            )
            run_store.consume_interaction_reply(request_id, interaction_id)
        options["__prompt_override"] = self._build_reply_prompt(
            options.get("__interactive_reply_payload")
        )
        if profile.kind == EngineInteractiveProfileKind.RESUMABLE:
            handle = run_store.get_engine_session_handle(request_id)
            if not handle:
                raise RuntimeError(
                    f"{InteractiveErrorCode.SESSION_RESUME_FAILED.value}: missing session handle"
                )
            options["__resume_session_handle"] = handle
            return
        wait_runtime = run_store.get_sticky_wait_runtime(request_id)
        if not wait_runtime:
            raise RuntimeError(
                f"{InteractiveErrorCode.INTERACTION_PROCESS_LOST.value}: missing sticky wait state"
            )
        deadline_raw = wait_runtime.get("wait_deadline_at")
        process_binding = wait_runtime.get("process_binding") or {}
        if not deadline_raw:
            raise RuntimeError(
                f"{InteractiveErrorCode.INTERACTION_PROCESS_LOST.value}: missing wait_deadline_at"
            )
        try:
            deadline = datetime.fromisoformat(deadline_raw)
        except Exception as exc:
            raise RuntimeError(
                f"{InteractiveErrorCode.INTERACTION_PROCESS_LOST.value}: invalid wait_deadline_at"
            ) from exc
        if datetime.utcnow() > deadline:
            raise RuntimeError(
                f"{InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value}: sticky wait expired"
            )
        if process_binding.get("alive") is False:
            raise RuntimeError(
                f"{InteractiveErrorCode.INTERACTION_PROCESS_LOST.value}: sticky process exited"
            )
        self._write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=run_store.get_pending_interaction(request_id) or {
                "interaction_id": interaction_id,
                "kind": "open_text",
                "prompt": "",
                "options": [],
                "ui_hints": {},
                "default_decision_policy": "engine_judgement",
                "required_fields": [],
            },
        )

    def _extract_pending_interaction(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        interaction_payload: Optional[Dict[str, Any]] = None
        if isinstance(payload.get("ask_user"), dict):
            interaction_payload = payload.get("ask_user")
        elif payload.get("action") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        elif payload.get("type") == "ask_user" and isinstance(payload.get("interaction"), dict):
            interaction_payload = payload.get("interaction")
        if interaction_payload is None:
            return None

        prompt = interaction_payload.get("prompt") or interaction_payload.get("question")
        if not isinstance(prompt, str) or not prompt.strip():
            return None
        interaction_id_raw = interaction_payload.get("interaction_id")
        if interaction_id_raw is None:
            return None
        try:
            interaction_id = int(interaction_id_raw)
        except Exception:
            return None
        if interaction_id <= 0:
            return None
        kind = self._normalize_interaction_kind_name(interaction_payload.get("kind"))
        options_payload = interaction_payload.get("options", [])
        options_normalized: list[dict[str, Any]] = []
        if isinstance(options_payload, list):
            for item in options_payload:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                options_normalized.append({"label": label, "value": item.get("value")})
        required_fields = interaction_payload.get("required_fields")
        if not isinstance(required_fields, list):
            required_fields = []
        ui_hints_raw = interaction_payload.get("ui_hints")
        ui_hints = ui_hints_raw if isinstance(ui_hints_raw, dict) else {}
        default_decision_policy_raw = interaction_payload.get("default_decision_policy")
        default_decision_policy = (
            default_decision_policy_raw.strip()
            if isinstance(default_decision_policy_raw, str) and default_decision_policy_raw.strip()
            else "engine_judgement"
        )
        return {
            "interaction_id": interaction_id,
            "kind": kind,
            "prompt": prompt.strip(),
            "options": options_normalized,
            "ui_hints": ui_hints,
            "default_decision_policy": default_decision_policy,
            "required_fields": required_fields,
            "context": interaction_payload.get("context"),
        }

    def _normalize_interaction_kind_name(self, raw_kind: Any) -> str:
        kind_name = str(raw_kind or "").strip().lower()
        alias_map = {
            "decision": "choose_one",
            "confirmation": "confirm",
            "clarification": "open_text",
        }
        kind_name = alias_map.get(kind_name, kind_name)
        allowed = {"choose_one", "confirm", "fill_fields", "open_text", "risk_ack"}
        if kind_name not in allowed:
            return "open_text"
        return kind_name

    def _looks_like_ask_user_payload(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if isinstance(payload.get("ask_user"), dict):
            return True
        if payload.get("action") == "ask_user":
            return True
        if payload.get("type") == "ask_user":
            return True
        if payload.get("outcome") == "ask_user":
            return True
        return False

    def _persist_waiting_interaction(
        self,
        *,
        adapter: Any,
        run_id: str,
        run_dir: Path,
        request_id: str,
        profile: EngineInteractiveProfile,
        interactive_require_user_reply: bool,
        pending_interaction: Dict[str, Any],
        raw_stdout: str,
    ) -> Optional[str]:
        run_store.set_pending_interaction(request_id, pending_interaction)
        run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        run_store.append_interaction_history(
            request_id=request_id,
            interaction_id=int(pending_interaction["interaction_id"]),
            event_type="ask_user",
            payload=pending_interaction,
        )
        if profile.kind == EngineInteractiveProfileKind.RESUMABLE:
            try:
                handle = adapter.extract_session_handle(
                    raw_stdout,
                    turn_index=int(pending_interaction["interaction_id"]),
                )
            except Exception:
                return InteractiveErrorCode.SESSION_RESUME_FAILED.value
            run_store.set_engine_session_handle(
                request_id,
                handle.model_dump(mode="json"),
            )
            self._write_interaction_mirror_files(
                run_dir=run_dir,
                request_id=request_id,
                pending_interaction=pending_interaction,
            )
            if not interactive_require_user_reply:
                wait_deadline = datetime.utcnow() + timedelta(seconds=profile.session_timeout_sec)
                run_store.set_sticky_wait_runtime(
                    request_id=request_id,
                    wait_deadline_at=wait_deadline.isoformat(),
                    process_binding={
                        "run_id": run_id,
                        "exec_session_id": f"{run_id}:{pending_interaction['interaction_id']}",
                        "alive": True,
                        "profile_kind": profile.kind.value,
                    },
                )
            return None

        wait_deadline = datetime.utcnow() + timedelta(seconds=profile.session_timeout_sec)
        run_store.set_sticky_wait_runtime(
            request_id=request_id,
            wait_deadline_at=wait_deadline.isoformat(),
            process_binding={
                "run_id": run_id,
                "exec_session_id": f"{run_id}:{pending_interaction['interaction_id']}",
                "alive": True,
                "profile_kind": profile.kind.value,
            },
        )
        self._write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=pending_interaction,
        )
        return None

    def _write_interaction_mirror_files(
        self,
        *,
        run_dir: Path,
        request_id: str,
        pending_interaction: Dict[str, Any],
    ) -> None:
        interactions_dir = run_dir / "interactions"
        interactions_dir.mkdir(parents=True, exist_ok=True)
        (interactions_dir / "pending.json").write_text(
            json.dumps(pending_interaction, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        history = run_store.list_interaction_history(request_id)
        history_path = interactions_dir / "history.jsonl"
        with history_path.open("w", encoding="utf-8") as f:
            for item in history:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        runtime_state = {
            "interactive_profile": run_store.get_interactive_profile(request_id),
            "effective_session_timeout_sec": run_store.get_effective_session_timeout(request_id),
            "sticky_wait_runtime": run_store.get_sticky_wait_runtime(request_id),
            "session_handle": run_store.get_engine_session_handle(request_id),
        }
        (interactions_dir / "runtime_state.json").write_text(
            json.dumps(runtime_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _schedule_sticky_watchdog(self, request_id: str, run_id: str, wait_deadline_at: str) -> None:
        self.cancel_sticky_watchdog(request_id)
        self._sticky_watchdog_tasks[request_id] = asyncio.create_task(
            self._sticky_watchdog_task(
                request_id=request_id,
                run_id=run_id,
                wait_deadline_at=wait_deadline_at,
            )
        )

    def cancel_sticky_watchdog(self, request_id: str) -> None:
        task = self._sticky_watchdog_tasks.pop(request_id, None)
        if task:
            task.cancel()

    async def _sticky_watchdog_task(
        self,
        *,
        request_id: str,
        run_id: str,
        wait_deadline_at: str,
    ) -> None:
        try:
            await self._run_sticky_watchdog_logic(
                request_id=request_id,
                run_id=run_id,
                wait_deadline_at=wait_deadline_at,
            )
        finally:
            self._sticky_watchdog_tasks.pop(request_id, None)

    async def _run_sticky_watchdog_logic(
        self,
        *,
        request_id: str,
        run_id: str,
        wait_deadline_at: str,
    ) -> None:
        try:
            deadline = datetime.fromisoformat(wait_deadline_at)
        except Exception:
            deadline = datetime.utcnow()
        sleep_sec = max(0.0, (deadline - datetime.utcnow()).total_seconds())
        try:
            await asyncio.sleep(sleep_sec)
        except asyncio.CancelledError:
            return

        request_record = run_store.get_request(request_id)
        if not request_record or request_record.get("run_id") != run_id:
            return
        run_dir = workspace_manager.get_run_dir(run_id)
        if not run_dir:
            return
        status_file = run_dir / "status.json"
        current_status = RunStatus.QUEUED
        if status_file.exists():
            payload = json.loads(status_file.read_text(encoding="utf-8"))
            current_status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        if current_status != RunStatus.WAITING_USER:
            return
        pending_interaction = run_store.get_pending_interaction(request_id)
        if pending_interaction is None:
            return

        runtime_options = request_record.get("runtime_options", {})
        interactive_require_user_reply = bool(
            runtime_options.get("interactive_require_user_reply", True)
        )
        profile = run_store.get_interactive_profile(request_id) or {}
        profile_kind = str(profile.get("kind", ""))

        if not interactive_require_user_reply:
            await self._resume_with_auto_decision(
                request_record=request_record,
                run_id=run_id,
                request_id=request_id,
                pending_interaction=pending_interaction,
                profile_kind=profile_kind,
            )
            return

        if profile_kind != EngineInteractiveProfileKind.STICKY_PROCESS.value:
            return

        error_payload = {
            "code": InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
            "message": "INTERACTION_WAIT_TIMEOUT: sticky wait expired",
        }
        self._update_status(
            run_dir,
            RunStatus.FAILED,
            error=error_payload,
            effective_session_timeout_sec=run_store.get_effective_session_timeout(request_id),
        )
        run_store.update_run_status(run_id, RunStatus.FAILED)
        sticky_runtime = run_store.get_sticky_wait_runtime(request_id) or {}
        process_binding = sticky_runtime.get("process_binding") or {}
        process_binding["alive"] = False
        wait_deadline = sticky_runtime.get("wait_deadline_at") or wait_deadline_at
        run_store.set_sticky_wait_runtime(
            request_id=request_id,
            wait_deadline_at=str(wait_deadline),
            process_binding=process_binding,
        )
        await concurrency_manager.release_slot()

    async def _resume_with_auto_decision(
        self,
        *,
        request_record: Dict[str, Any],
        run_id: str,
        request_id: str,
        pending_interaction: Dict[str, Any],
        profile_kind: str,
    ) -> None:
        interaction_id_obj = pending_interaction.get("interaction_id")
        if isinstance(interaction_id_obj, int):
            interaction_id = interaction_id_obj
        elif isinstance(interaction_id_obj, str):
            try:
                interaction_id = int(interaction_id_obj)
            except ValueError:
                return
        else:
            return
        if interaction_id <= 0:
            return

        default_policy_obj = pending_interaction.get("default_decision_policy")
        default_policy = (
            default_policy_obj.strip()
            if isinstance(default_policy_obj, str) and default_policy_obj.strip()
            else "engine_judgement"
        )
        auto_reply_payload = {
            "source": "auto_decide_timeout",
            "interaction_id": interaction_id,
            "reason": "user_no_reply",
            "policy": default_policy,
            "instruction": (
                "User did not respond in time. Continue with your best judgement "
                "based on the current context."
            ),
        }
        reply_state = run_store.submit_interaction_reply(
            request_id=request_id,
            interaction_id=interaction_id,
            response=auto_reply_payload,
            idempotency_key=f"auto-timeout:{interaction_id}",
        )
        if reply_state not in {"accepted", "idempotent"}:
            return

        is_sticky = profile_kind == EngineInteractiveProfileKind.STICKY_PROCESS.value
        next_status = RunStatus.RUNNING if is_sticky else RunStatus.QUEUED
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir is None:
            return
        self._update_status(
            run_dir,
            next_status,
            effective_session_timeout_sec=run_store.get_effective_session_timeout(request_id),
        )
        run_store.update_run_status(run_id, next_status)

        options = {
            **request_record.get("engine_options", {}),
            **request_record.get("runtime_options", {}),
            "__interactive_reply_payload": auto_reply_payload,
            "__interactive_reply_interaction_id": interaction_id,
            "__interactive_resolution_mode": "auto_decide_timeout",
            "__interactive_auto_reason": "user_no_reply",
            "__interactive_auto_policy": default_policy,
        }
        if is_sticky:
            options["__sticky_slot_held"] = True
            sticky_runtime = run_store.get_sticky_wait_runtime(request_id) or {}
            process_binding = sticky_runtime.get("process_binding") or {}
            process_binding["alive"] = True
            timeout_sec = run_store.get_effective_session_timeout(request_id) or 1
            refreshed_deadline = (
                datetime.utcnow() + timedelta(seconds=max(1, int(timeout_sec)))
            ).isoformat()
            run_store.set_sticky_wait_runtime(
                request_id=request_id,
                wait_deadline_at=refreshed_deadline,
                process_binding=process_binding,
            )
        await self.run_job(
            run_id=run_id,
            skill_id=str(request_record["skill_id"]),
            engine_name=str(request_record["engine"]),
            options=options,
            cache_key=None,
        )

    async def recover_incomplete_runs_on_startup(self) -> None:
        records = run_store.list_incomplete_runs()
        if not records:
            concurrency_manager.reset_runtime_state()
            return

        for record in records:
            await self._recover_single_incomplete_run(record)

        await self._cleanup_orphan_runtime_bindings(records)
        active_run_dirs: list[Path] = []
        for run_id in run_store.list_active_run_ids():
            run_dir = workspace_manager.get_run_dir(run_id)
            if run_dir:
                active_run_dirs.append(run_dir)
        try:
            run_folder_trust_manager.cleanup_stale_entries(active_run_dirs)
        except Exception:
            logger.warning("Startup stale trust cleanup failed", exc_info=True)
        concurrency_manager.reset_runtime_state()

    async def _recover_single_incomplete_run(self, record: Dict[str, Any]) -> None:
        request_id = str(record.get("request_id") or "")
        run_id = str(record.get("run_id") or "")
        run_status_raw = record.get("run_status")
        engine_name = str(record.get("engine") or "")
        if not request_id or not run_id or not isinstance(run_status_raw, str):
            return
        try:
            run_status = RunStatus(run_status_raw)
        except ValueError:
            return

        if run_status == RunStatus.WAITING_USER:
            profile_raw = record.get("interactive_profile")
            profile_kind = (
                str(profile_raw.get("kind", "")).strip()
                if isinstance(profile_raw, dict)
                else ""
            )
            if profile_kind == EngineInteractiveProfileKind.RESUMABLE.value:
                pending = run_store.get_pending_interaction(request_id)
                handle = run_store.get_engine_session_handle(request_id)
                if isinstance(pending, dict) and self._is_valid_session_handle(handle):
                    run_store.update_run_status(run_id, RunStatus.WAITING_USER)
                    run_store.set_recovery_info(
                        run_id,
                        recovery_state="recovered_waiting",
                        recovery_reason="resumable_waiting_preserved",
                    )
                    return
                await self._mark_restart_reconciled_failed(
                    request_id=request_id,
                    run_id=run_id,
                    engine_name=engine_name,
                    error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                    reason="missing pending interaction or session handle after restart",
                )
                return
            if profile_kind == EngineInteractiveProfileKind.STICKY_PROCESS.value:
                await self._mark_restart_reconciled_failed(
                    request_id=request_id,
                    run_id=run_id,
                    engine_name=engine_name,
                    error_code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                    reason="sticky process context cannot survive orchestrator restart",
                )
                return
            await self._mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
                reason="waiting_user run missing or invalid interactive_profile",
            )
            return

        if run_status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            await self._mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
                reason=f"{run_status.value} run interrupted by orchestrator restart",
            )

    async def _mark_restart_reconciled_failed(
        self,
        *,
        request_id: str,
        run_id: str,
        engine_name: str,
        error_code: str,
        reason: str,
    ) -> None:
        message = f"{error_code}: {reason}"
        run_dir = workspace_manager.get_run_dir(run_id)
        if run_dir:
            self._update_status(
                run_dir,
                RunStatus.FAILED,
                error={"code": error_code, "message": message},
                effective_session_timeout_sec=run_store.get_effective_session_timeout(request_id),
            )
        run_store.update_run_status(run_id, RunStatus.FAILED)
        run_store.set_recovery_info(
            run_id,
            recovery_state="failed_reconciled",
            recovery_reason=reason,
        )
        run_store.clear_pending_interaction(request_id)
        run_store.clear_engine_session_handle(request_id)
        run_store.clear_sticky_wait_runtime(request_id)
        self.cancel_sticky_watchdog(request_id)
        adapter = self.adapters.get(engine_name)
        if adapter is not None:
            with contextlib.suppress(Exception):
                await adapter.cancel_run_process(run_id)

    async def _cleanup_orphan_runtime_bindings(self, records: List[Dict[str, Any]]) -> None:
        active_run_ids = set(run_store.list_active_run_ids())
        for record in records:
            request_id = str(record.get("request_id") or "")
            if not request_id:
                continue
            process_binding = record.get("process_binding")
            if not isinstance(process_binding, dict):
                continue
            bound_run_id = str(process_binding.get("run_id") or "")
            if not bound_run_id or bound_run_id in active_run_ids:
                continue
            engine_name = str(record.get("engine") or "")
            adapter = self.adapters.get(engine_name)
            if adapter is not None:
                with contextlib.suppress(Exception):
                    await adapter.cancel_run_process(bound_run_id)
            run_store.clear_engine_session_handle(request_id)
            run_store.clear_sticky_wait_runtime(request_id)

    def _is_valid_session_handle(self, handle: Any) -> bool:
        if not isinstance(handle, dict):
            return False
        try:
            parsed = EngineSessionHandle.model_validate(handle)
        except Exception:
            return False
        return bool(parsed.handle_value)

    def _build_reply_prompt(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False)

    def _error_from_exception(self, exc: Exception) -> Dict[str, Any]:
        text = str(exc)
        for code in (
            InteractiveErrorCode.SESSION_RESUME_FAILED.value,
            InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
            InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
            InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
        ):
            if text.startswith(code):
                return {"code": code, "message": text}
        return {"message": text}

job_orchestrator = JobOrchestrator()

logger = logging.getLogger(__name__)
