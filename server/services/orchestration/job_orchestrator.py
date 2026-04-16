import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import ValidationError
from server.models import (
    EngineSessionHandle,
    EngineInteractiveProfile,
    ExecutionMode,
    InteractiveErrorCode,
    RunStatus,
    SkillManifest,
)
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.skill.skill_registry import skill_registry
from server.services.engine_management.engine_adapter_registry import engine_adapter_registry
from server.services.platform.schema_validator import schema_validator
from server.services.orchestration.run_store import run_store
from server.services.platform.concurrency_manager import concurrency_manager
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager
from server.services.orchestration.run_bundle_service import RunBundleService
from server.services.orchestration.run_filesystem_snapshot_service import (
    RunFilesystemSnapshotService,
)
from server.services.orchestration.run_audit_service import RunAuditService
from server.services.orchestration.run_interaction_lifecycle_service import (
    RunInteractionLifecycleService,
)
from server.services.orchestration.run_recovery_service import RunRecoveryService
from server.services.orchestration.run_job_lifecycle_service import (
    RunJobLifecycleService,
    RunJobRequest,
)
from server.services.orchestration.run_attempt_preparation_service import (
    RunAttemptPreparationService,
    resolve_attempt_number,
    resolve_session_timeout_seconds,
)
from server.services.orchestration.run_auth_orchestration_service import (
    RunAuthOrchestrationService,
    run_auth_orchestration_service,
)
from server.services.orchestration.run_attempt_execution_service import (
    RunAttemptExecutionService,
)
from server.services.orchestration.run_attempt_outcome_service import (
    RunAttemptOutcomeService,
)
from server.services.orchestration.run_attempt_projection_finalizer import (
    RunAttemptProjectionFinalizer,
)
from server.services.orchestration.run_attempt_audit_finalizer import (
    RunAttemptAuditFinalizer,
)
from server.services.orchestration.run_projection_service import run_projection_service
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
)
from server.runtime.logging.structured_trace import log_event
from server.config import config


@dataclass
class OrchestratorDeps:
    agent_cli_manager: AgentCliManager | None = None
    adapters: dict[str, Any] | None = None
    run_store_backend: Any | None = None
    workspace_backend: Any | None = None
    concurrency_backend: Any | None = None
    trust_manager_backend: Any | None = None
    bundle_service: RunBundleService | None = None
    snapshot_service: RunFilesystemSnapshotService | None = None
    audit_service: RunAuditService | None = None
    interaction_service: RunInteractionLifecycleService | None = None
    recovery_service: RunRecoveryService | None = None
    run_job_lifecycle_service: RunJobLifecycleService | None = None
    auth_orchestration_service: RunAuthOrchestrationService | None = None
    run_attempt_preparation_service: RunAttemptPreparationService | None = None
    run_attempt_execution_service: RunAttemptExecutionService | None = None
    run_attempt_outcome_service: RunAttemptOutcomeService | None = None
    run_attempt_projection_finalizer: RunAttemptProjectionFinalizer | None = None
    run_attempt_audit_finalizer: RunAttemptAuditFinalizer | None = None


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
    def __init__(self, deps: OrchestratorDeps | None = None):
        self.deps = deps or OrchestratorDeps()
        self.agent_cli_manager = self.deps.agent_cli_manager or AgentCliManager()
        self.adapters = self.deps.adapters or engine_adapter_registry.adapter_map()
        self.bundle_service = self.deps.bundle_service or RunBundleService()
        self.snapshot_service = self.deps.snapshot_service or RunFilesystemSnapshotService(
            bundle_service=self.bundle_service
        )
        self.audit_service = self.deps.audit_service or RunAuditService(
            snapshot_service=self.snapshot_service
        )
        self.interaction_service = self.deps.interaction_service or RunInteractionLifecycleService()
        self.recovery_service = self.deps.recovery_service or RunRecoveryService()
        self.auth_orchestration_service = (
            self.deps.auth_orchestration_service or run_auth_orchestration_service
        )
        self.run_attempt_preparation_service = (
            self.deps.run_attempt_preparation_service or RunAttemptPreparationService()
        )
        self.run_attempt_execution_service = (
            self.deps.run_attempt_execution_service or RunAttemptExecutionService()
        )
        self.run_attempt_outcome_service = (
            self.deps.run_attempt_outcome_service or RunAttemptOutcomeService()
        )
        self.run_attempt_projection_finalizer = (
            self.deps.run_attempt_projection_finalizer or RunAttemptProjectionFinalizer()
        )
        self.run_attempt_audit_finalizer = (
            self.deps.run_attempt_audit_finalizer or RunAttemptAuditFinalizer()
        )
        self.run_job_lifecycle_service = (
            self.deps.run_job_lifecycle_service or RunJobLifecycleService()
        )

    def _run_store_backend(self) -> Any:
        return self.deps.run_store_backend or run_store

    def _workspace_backend(self) -> Any:
        return self.deps.workspace_backend or workspace_manager

    def _concurrency_backend(self) -> Any:
        return self.deps.concurrency_backend or concurrency_manager

    def _trust_manager_backend(self) -> Any:
        return self.deps.trust_manager_backend or run_folder_trust_manager

    async def run_job(
        self,
        run_id: str,
        skill_id: str,
        engine_name: str,
        options: Dict[str, Any],
        cache_key: Optional[str] = None,
        skill_override: Optional[SkillManifest] = None,
        temp_request_id: Optional[str] = None,
    ) -> None:
        log_event(
            logger,
            event="run.lifecycle.queued",
            phase="orchestrator_dispatch",
            outcome="start",
            request_id=None,
            run_id=run_id,
            engine=engine_name,
        )
        request = RunJobRequest(
            run_id=run_id,
            skill_id=skill_id,
            engine_name=engine_name,
            options=options,
            cache_key=cache_key,
            skill_override=skill_override,
            temp_request_id=temp_request_id,
        )
        await self.run_job_lifecycle_service.run(
            orchestrator=self,
            request=request,
        )

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
        run_store = self._run_store_backend()
        changed = await run_store.set_cancel_requested(run_id, True)
        if status == RunStatus.RUNNING:
            adapter = self.adapters.get(engine_name)
            if adapter is not None:
                with contextlib.suppress(OSError, RuntimeError, TypeError, ValueError):
                    await adapter.cancel_run_process(run_id)
        if request_id:
            with contextlib.suppress(OSError, RuntimeError, TypeError, ValueError):
                await self.auth_orchestration_service.cancel_request_auth_sessions(
                    request_id=request_id,
                    run_store_backend=run_store,
                    terminal_reason="run_canceled",
                )

        canceled_error = self._build_canceled_error()
        request_record = (
            await run_store.get_request(request_id) if request_id else None
        )
        effective_session_timeout_sec = (
            (await run_store.get_effective_session_timeout(request_id)) if request_id else None
        )
        if request_id:
            await run_projection_service.write_terminal_projection(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_id,
                status=RunStatus.CANCELED,
                terminal_result={
                    "data": None,
                    "artifacts": [],
                    "repair_level": "none",
                    "validation_warnings": [],
                    "error": canceled_error,
                },
                request_record=request_record,
                effective_session_timeout_sec=effective_session_timeout_sec,
                error=canceled_error,
            )
        else:
            self._write_canceled_result(run_dir, canceled_error)
            self._update_status(
                run_dir,
                RunStatus.CANCELED,
                error=canceled_error,
                effective_session_timeout_sec=effective_session_timeout_sec,
            )
        await run_store.update_run_status(run_id, RunStatus.CANCELED)

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
        }
        result_path = run_dir / "result" / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result_path

    def _write_failed_result(self, run_dir: Optional[Path], error: Dict[str, Any]) -> Optional[Path]:
        if run_dir is None:
            return None
        result_payload: Dict[str, Any] = {
            "status": RunStatus.FAILED.value,
            "data": None,
            "artifacts": [],
            "repair_level": "none",
            "validation_warnings": [],
            "error": error,
            "pending_interaction": None,
            "pending_auth_method_selection": None,
            "pending_auth": None,
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
        state_file = run_dir / ".state" / "state.json"
        warnings_list = warnings or []
        status_data = {}
        if state_file.exists():
            try:
                status_data = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                status_data = {}
        if not isinstance(status_data, dict):
            status_data = {}
        runtime_obj = status_data.get("runtime")
        runtime_payload: Dict[str, Any] = dict(runtime_obj) if isinstance(runtime_obj, dict) else {}
        runtime_payload["effective_session_timeout_sec"] = effective_session_timeout_sec
        status_data.update(
            {
                "status": status.value if isinstance(status, RunStatus) else str(status),
                "updated_at": str(datetime.now()),
                "error": error,
                "warnings": warnings_list,
                "runtime": runtime_payload,
            }
        )
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_latest_run_id(self, run_id: str):
        """Updates the latest_run_id file in the runs directory."""
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        try:
            with open(runs_dir / "latest_run_id", "w") as f:
                f.write(run_id)
        except OSError:
            logger.exception("Failed to update latest_run_id")

    def build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
        return self.bundle_service.build_run_bundle(run_dir=run_dir, debug=debug)

    def _resolve_hard_timeout_seconds(self, options: Dict[str, Any]) -> int:
        default_timeout = int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS)
        candidate = options.get("hard_timeout_seconds", default_timeout)
        try:
            parsed = int(candidate)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass
        return default_timeout

    def _append_internal_schema_warning(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        schema_path: str,
        detail: str,
    ) -> None:
        self.audit_service.append_internal_schema_warning(
            run_dir=run_dir,
            attempt_number=attempt_number,
            schema_path=schema_path,
            detail=detail,
        )

    async def _resolve_interactive_profile(
        self,
        request_id: str,
        engine_name: str,
        options: Dict[str, Any],
    ) -> EngineInteractiveProfile:
        run_store = self._run_store_backend()
        existing = await run_store.get_interactive_profile(request_id)
        if existing:
            profile = EngineInteractiveProfile.model_validate(existing)
            if await run_store.get_effective_session_timeout(request_id) is None:
                await run_store.set_effective_session_timeout(request_id, profile.session_timeout_sec)
            return profile
        session_timeout_sec = resolve_session_timeout_seconds(options)
        profile = self.agent_cli_manager.resolve_interactive_profile(
            engine=engine_name,
            session_timeout_sec=session_timeout_sec,
        )
        await run_store.set_effective_session_timeout(request_id, session_timeout_sec)
        await run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        return profile

    async def _auto_decide_after_timeout(
        self,
        *,
        request_id: str,
        run_id: str,
        delay_sec: int,
    ) -> None:
        run_store = self._run_store_backend()
        workspace_manager = self._workspace_backend()
        await self.interaction_service.auto_decide_after_timeout(
            request_id=request_id,
            run_id=run_id,
            delay_sec=delay_sec,
            run_store_backend=run_store,
            workspace_backend=workspace_manager,
            update_status=self._update_status,
            run_job_callback=self.run_job,
            append_internal_schema_warning=self._append_internal_schema_warning,
            resolve_attempt_number=lambda **kwargs: resolve_attempt_number(
                run_store_backend=run_store,
                **kwargs,
            ),
        )

    async def _resume_with_auto_decision(
        self,
        *,
        request_record: Dict[str, Any],
        run_id: str,
        request_id: str,
        pending_interaction: Dict[str, Any],
    ) -> None:
        run_store = self._run_store_backend()
        workspace_manager = self._workspace_backend()
        await self.interaction_service.resume_with_auto_decision(
            request_record=request_record,
            run_id=run_id,
            request_id=request_id,
            pending_interaction=pending_interaction,
            run_store_backend=run_store,
            workspace_backend=workspace_manager,
            update_status=self._update_status,
            run_job_callback=self.run_job,
            append_internal_schema_warning=self._append_internal_schema_warning,
            resolve_attempt_number=lambda **kwargs: resolve_attempt_number(
                run_store_backend=run_store,
                **kwargs,
            ),
        )

    async def recover_incomplete_runs_on_startup(self) -> None:
        await self.recovery_service.recover_incomplete_runs_on_startup(
            run_store_backend=self._run_store_backend(),
            concurrency_backend=self._concurrency_backend(),
            workspace_backend=self._workspace_backend(),
            trust_manager_backend=self._trust_manager_backend(),
            recover_single=self._recover_single_incomplete_run,
            cleanup_orphan_bindings=self._cleanup_orphan_runtime_bindings,
        )

    async def _recover_single_incomplete_run(self, record: Dict[str, Any]) -> None:
        await self.recovery_service.recover_single_incomplete_run(
            record=record,
            run_store_backend=self._run_store_backend(),
            is_valid_session_handle=self._is_valid_session_handle,
            mark_restart_reconciled_failed=self._mark_restart_reconciled_failed,
            resume_run_job=self.run_job,
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
        await self.recovery_service.mark_restart_reconciled_failed(
            request_id=request_id,
            run_id=run_id,
            engine_name=engine_name,
            error_code=error_code,
            reason=reason,
            run_store_backend=self._run_store_backend(),
            workspace_backend=self._workspace_backend(),
            update_status=self._update_status,
            adapters=self.adapters,
        )

    async def _cleanup_orphan_runtime_bindings(self, records: List[Dict[str, Any]]) -> None:
        await self.recovery_service.cleanup_orphan_runtime_bindings(records)

    def _is_valid_session_handle(self, handle: Any) -> bool:
        if not isinstance(handle, dict):
            return False
        try:
            parsed = EngineSessionHandle.model_validate(handle)
        except ValidationError:
            return False
        return bool(parsed.handle_value)

    def _build_reply_prompt(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False)

    def _error_from_exception(self, exc: Exception) -> Dict[str, Any]:
        if isinstance(exc, ProtocolSchemaViolation):
            return {
                "code": InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value,
                "message": (
                    f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
                ),
            }
        text = str(exc)
        for code in (
            InteractiveErrorCode.SESSION_RESUME_FAILED.value,
            InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
            InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value,
        ):
            if text.startswith(code):
                return {"code": code, "message": text}
        return {"message": text}

job_orchestrator = JobOrchestrator()

logger = logging.getLogger(__name__)
