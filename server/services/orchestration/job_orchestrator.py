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
    AdapterTurnOutcome,
    EngineSessionHandle,
    EngineInteractiveProfile,
    ExecutionMode,
    InteractiveErrorCode,
    OrchestratorEventType,
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
from server.services.orchestration.run_auth_orchestration_service import (
    RunAuthOrchestrationService,
    run_auth_orchestration_service,
)
from server.services.orchestration.run_projection_service import run_projection_service
from server.runtime.auth_detection.service import (
    AuthDetectionService,
    auth_detection_service,
)
from server.runtime.session.timeout import resolve_interactive_reply_timeout
from server.services.engine_management.engine_policy import apply_engine_policy_to_manifest
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
)
from server.runtime.protocol.parse_utils import extract_fenced_or_plain_json
from server.runtime.protocol.event_protocol import translate_orchestrator_event_to_fcmp_specs
from server.runtime.protocol.factories import make_fcmp_event
from server.runtime.protocol.live_publish import fcmp_event_publisher
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
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
    auth_detection_service: AuthDetectionService | None = None
    auth_orchestration_service: RunAuthOrchestrationService | None = None


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
        self.auth_detection_service = (
            self.deps.auth_detection_service or auth_detection_service
        )
        self.auth_orchestration_service = (
            self.deps.auth_orchestration_service or run_auth_orchestration_service
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

    def _load_skill_from_run_dir(
        self,
        *,
        run_dir: Path,
        skill_id: str,
        engine_name: str,
    ) -> Optional[SkillManifest]:
        workspace_prefix = {
            "codex": ".codex",
            "gemini": ".gemini",
            "iflow": ".iflow",
            "opencode": ".opencode",
        }.get(engine_name, f".{engine_name}")
        skill_dir = run_dir / workspace_prefix / "skills" / skill_id
        runner_path = skill_dir / "assets" / "runner.json"
        if not runner_path.exists() or not runner_path.is_file():
            return None
        try:
            data = json.loads(runner_path.read_text(encoding="utf-8"))
            data = infer_manifest_artifacts(data, skill_dir)
            apply_engine_policy_to_manifest(data)
            return SkillManifest(**data, path=skill_dir)
        except (OSError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
            logger.warning(
                "Failed to load skill manifest from run directory for resume: run_id=%s skill_id=%s",
                run_dir.name,
                skill_id,
                exc_info=True,
            )
            return None

    def build_run_bundle(self, run_dir: Path, debug: bool = False) -> str:
        return self.bundle_service.build_run_bundle(run_dir=run_dir, debug=debug)

    def _build_run_bundle(self, run_dir: Path, debug: bool) -> str:
        # Compatibility wrapper for existing internal callers/tests.
        return self.build_run_bundle(run_dir=run_dir, debug=debug)

    def _bundle_candidates(self, run_dir: Path, debug: bool, bundle_path: Path, manifest_path: Path) -> list[Path]:
        return self.bundle_service.bundle_candidates(
            run_dir=run_dir,
            debug=debug,
            bundle_path=bundle_path,
            manifest_path=manifest_path,
        )

    def _hash_file(self, path: Path) -> str:
        return self.bundle_service.hash_file(path)

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

    def _parse_runtime_stream_for_auth_detection(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
    ) -> Dict[str, Any] | None:
        if adapter is None or not hasattr(adapter, "parse_runtime_stream"):
            return None
        try:
            parsed = adapter.parse_runtime_stream(
                stdout_raw=raw_stdout.encode("utf-8", errors="replace"),
                stderr_raw=raw_stderr.encode("utf-8", errors="replace"),
                pty_raw=b"",
            )
        except (OSError, RuntimeError, TypeError, ValueError, LookupError) as exc:
            logger.warning(
                "Failed to parse runtime stream for auth detection: adapter=%s",
                getattr(adapter, "__class__", type(adapter)).__name__,
                exc_info=True,
            )
            return {
                "parser": "auth_detection_fallback",
                "confidence": 0.0,
                "session_id": None,
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [f"AUTH_DETECTION_PARSE_FAILED:{type(exc).__name__}"],
                "structured_types": [],
            }
        return parsed if isinstance(parsed, dict) else None

    async def _resolve_attempt_number(self, *, request_id: Optional[str], is_interactive: bool) -> int:
        if not request_id or not is_interactive:
            return 1
        run_store = self._run_store_backend()
        interaction_count = await run_store.get_interaction_count(request_id)
        return max(1, int(interaction_count) + 1)

    def _capture_filesystem_snapshot(self, run_dir: Path) -> Dict[str, Dict[str, Any]]:
        return self.snapshot_service.capture_filesystem_snapshot(run_dir)

    def _diff_filesystem_snapshot(
        self,
        before_snapshot: Dict[str, Dict[str, Any]],
        after_snapshot: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        return self.snapshot_service.diff_filesystem_snapshot(before_snapshot, after_snapshot)

    def _find_done_markers(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
        turn_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.audit_service.find_done_markers(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            turn_payload=turn_payload,
        )

    def _contains_done_marker_in_stream(
        self,
        *,
        adapter: Any | None,
        raw_stdout: str,
        raw_stderr: str,
    ) -> bool:
        return self.audit_service.contains_done_marker_in_stream(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

    def _classify_completion(
        self,
        *,
        status: Optional[RunStatus],
        process_exit_code: Optional[int],
        done_info: Dict[str, Any],
        validation_warnings: List[str],
        terminal_error_code: Optional[str],
    ) -> Dict[str, Any]:
        return self.audit_service.classify_completion(
            status=status,
            process_exit_code=process_exit_code,
            done_info=done_info,
            validation_warnings=validation_warnings,
            terminal_error_code=terminal_error_code,
        )

    def _write_attempt_audit_artifacts(
        self,
        *,
        run_dir: Path,
        run_id: str,
        request_id: Optional[str],
        engine_name: str,
        execution_mode: str,
        attempt_number: int,
        started_at: datetime,
        finished_at: datetime,
        status: Optional[RunStatus],
        fs_before_snapshot: Dict[str, Dict[str, Any]],
        process_exit_code: Optional[int],
        process_failure_reason: Optional[str],
        process_raw_stdout: str,
        process_raw_stderr: str,
        adapter: Any | None,
        turn_payload: Dict[str, Any],
        validation_warnings: List[str],
        terminal_error_code: Optional[str],
        options: Dict[str, Any],
        auth_detection: Dict[str, Any] | None = None,
        auth_session: Dict[str, Any] | None = None,
    ) -> None:
        self.audit_service.write_attempt_audit_artifacts(
            run_dir=run_dir,
            run_id=run_id,
            request_id=request_id,
            engine_name=engine_name,
            execution_mode=execution_mode,
            attempt_number=attempt_number,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            fs_before_snapshot=fs_before_snapshot,
            process_exit_code=process_exit_code,
            process_failure_reason=process_failure_reason,
            process_raw_stdout=process_raw_stdout,
            process_raw_stderr=process_raw_stderr,
            adapter=adapter,
            turn_payload=turn_payload,
            validation_warnings=validation_warnings,
            terminal_error_code=terminal_error_code,
            options=options,
            auth_detection=auth_detection,
            auth_session=auth_session,
        )

    def _append_orchestrator_event(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        category: str,
        type_name: str,
        data: Dict[str, Any],
        engine_name: Optional[str] = None,
    ) -> None:
        self.audit_service.append_orchestrator_event(
            run_dir=run_dir,
            attempt_number=attempt_number,
            category=category,
            type_name=type_name,
            data=data,
        )
        resolved_engine = self._resolve_orchestrator_event_engine(
            run_dir=run_dir,
            data=data,
            engine_name=engine_name,
        )
        for spec in translate_orchestrator_event_to_fcmp_specs(
            engine=resolved_engine,
            type_name=type_name,
            data=data,
            updated_at=datetime.utcnow().isoformat(),
            default_attempt_number=attempt_number,
        ):
            event = make_fcmp_event(
                run_id=run_dir.name,
                seq=1,
                engine=resolved_engine,
                type_name=str(spec["type_name"]),
                data=dict(spec["data"]),
                attempt_number=attempt_number,
                ts=datetime.utcnow(),
            )
            fcmp_event_publisher.publish(run_dir=run_dir, event=event)

    def _resolve_orchestrator_event_engine(
        self,
        *,
        run_dir: Path,
        data: Dict[str, Any],
        engine_name: Optional[str],
    ) -> str:
        if isinstance(engine_name, str) and engine_name.strip():
            return engine_name.strip()
        engine_obj = data.get("engine")
        if isinstance(engine_obj, str) and engine_obj.strip():
            return engine_obj.strip()
        live_payload = fcmp_live_journal.replay(run_id=run_dir.name, after_seq=0)
        live_events = live_payload.get("events")
        if isinstance(live_events, list):
            for row in reversed(live_events):
                if not isinstance(row, dict):
                    continue
                row_engine = row.get("engine")
                if isinstance(row_engine, str) and row_engine.strip():
                    return row_engine.strip()
        return "unknown"

    def _next_orchestrator_event_seq(self, event_path: Path) -> int:
        return self.audit_service.next_orchestrator_event_seq(event_path)

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

    def _resolve_session_timeout_seconds(self, options: Dict[str, Any]) -> int:
        return resolve_interactive_reply_timeout(
            options,
            default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
        ).value

    def _resolve_interactive_auto_reply(
        self,
        *,
        options: Dict[str, Any],
        request_record: Dict[str, Any],
    ) -> bool:
        if "interactive_auto_reply" in options:
            value = options.get("interactive_auto_reply")
            if isinstance(value, bool):
                return value
        runtime_options = request_record.get(
            "effective_runtime_options",
            request_record.get("runtime_options", {}),
        )
        value = runtime_options.get("interactive_auto_reply", False)
        return bool(value)

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
        session_timeout_sec = self._resolve_session_timeout_seconds(options)
        profile = self.agent_cli_manager.resolve_interactive_profile(
            engine=engine_name,
            session_timeout_sec=session_timeout_sec,
        )
        await run_store.set_effective_session_timeout(request_id, session_timeout_sec)
        await run_store.set_interactive_profile(request_id, profile.model_dump(mode="json"))
        return profile

    async def _inject_interactive_resume_context(
        self,
        request_id: str,
        profile: EngineInteractiveProfile,
        options: Dict[str, Any],
        run_dir: Path,
    ) -> None:
        run_store = self._run_store_backend()
        await self.interaction_service.inject_interactive_resume_context(
            request_id=request_id,
            profile=profile,
            options=options,
            run_dir=run_dir,
            run_store_backend=run_store,
            append_internal_schema_warning=self._append_internal_schema_warning,
            resolve_attempt_number=self._resolve_attempt_number,
            build_reply_prompt=self._build_reply_prompt,
        )

    def _extract_pending_interaction(
        self,
        payload: Dict[str, Any],
        *,
        fallback_interaction_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.interaction_service.extract_pending_interaction(
            payload,
            fallback_interaction_id=fallback_interaction_id,
        )

    def _infer_pending_interaction(
        self,
        payload: Dict[str, Any],
        *,
        fallback_interaction_id: int,
    ) -> Optional[Dict[str, Any]]:
        return self.interaction_service.infer_pending_interaction(
            payload,
            fallback_interaction_id=fallback_interaction_id,
        )

    def _infer_pending_interaction_from_runtime_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: int,
    ) -> Optional[Dict[str, Any]]:
        return self.interaction_service.infer_pending_interaction_from_runtime_stream(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            fallback_interaction_id=fallback_interaction_id,
        )

    def _strip_prompt_yaml_blocks(self, text: str) -> str:
        return self.interaction_service.strip_prompt_yaml_blocks(text)

    def _normalize_interaction_prompt(self, raw_prompt: Any) -> str:
        return self.interaction_service.normalize_interaction_prompt(raw_prompt)

    def _normalize_interaction_kind_name(self, raw_kind: Any) -> str:
        return self.interaction_service.normalize_interaction_kind_name(raw_kind)

    def _looks_like_direct_interaction_payload(self, payload: Dict[str, Any]) -> bool:
        return self.interaction_service.looks_like_direct_interaction_payload(payload)

    def _extract_pending_interaction_from_stream(
        self,
        *,
        adapter: Any,
        raw_stdout: str,
        raw_stderr: str,
        fallback_interaction_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        return self.interaction_service.extract_pending_interaction_from_stream(
            adapter=adapter,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            fallback_interaction_id=fallback_interaction_id,
        )

    def _strip_done_marker_for_output_validation(
        self,
        payload: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        return self.interaction_service.strip_done_marker_for_output_validation(payload)

    def _materialize_turn_result_payload(self, turn_result: Any | None) -> Dict[str, Any] | None:
        if turn_result is None:
            return None
        outcome = getattr(turn_result, "outcome", None)
        if outcome == AdapterTurnOutcome.FINAL:
            final_data = getattr(turn_result, "final_data", None)
            return dict(final_data) if isinstance(final_data, dict) else None
        if outcome == AdapterTurnOutcome.ASK_USER:
            interaction = getattr(turn_result, "interaction", None)
            if interaction is None:
                return None
            interaction_payload = interaction.model_dump(mode="json")
            return {
                "outcome": AdapterTurnOutcome.ASK_USER.value,
                "action": AdapterTurnOutcome.ASK_USER.value,
                "ask_user": interaction_payload,
                "interaction": interaction_payload,
            }
        return None

    def _resolve_structured_output_payload(
        self,
        *,
        result: Any,
        runtime_parse_result: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        payload = self._materialize_turn_result_payload(getattr(result, "turn_result", None))
        if isinstance(payload, dict):
            return payload

        if not isinstance(runtime_parse_result, dict):
            return None
        assistant_messages = runtime_parse_result.get("assistant_messages")
        if not isinstance(assistant_messages, list):
            return None
        for item in reversed(assistant_messages):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            parsed = extract_fenced_or_plain_json(text)
            if isinstance(parsed, dict):
                return parsed
        return None

    async def _persist_waiting_interaction(
        self,
        *,
        adapter: Any,
        run_id: str,
        run_dir: Path,
        request_id: str,
        attempt_number: int,
        profile: EngineInteractiveProfile,
        interactive_auto_reply: bool,
        pending_interaction: Dict[str, Any],
        raw_runtime_output: str,
    ) -> Optional[str]:
        run_store = self._run_store_backend()
        return await self.interaction_service.persist_waiting_interaction(
            adapter=adapter,
            run_id=run_id,
            run_dir=run_dir,
            request_id=request_id,
            attempt_number=attempt_number,
            profile=profile,
            interactive_auto_reply=interactive_auto_reply,
            pending_interaction=pending_interaction,
            raw_runtime_output=raw_runtime_output,
            run_store_backend=run_store,
            append_internal_schema_warning=self._append_internal_schema_warning,
            append_orchestrator_event=self._append_orchestrator_event,
        )

    async def _write_interaction_mirror_files(
        self,
        *,
        run_dir: Path,
        request_id: str,
        pending_interaction: Dict[str, Any],
    ) -> None:
        run_store = self._run_store_backend()
        await self.interaction_service.write_interaction_mirror_files(
            run_dir=run_dir,
            request_id=request_id,
            pending_interaction=pending_interaction,
            run_store_backend=run_store,
        )

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
            resolve_attempt_number=self._resolve_attempt_number,
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
            resolve_attempt_number=self._resolve_attempt_number,
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
