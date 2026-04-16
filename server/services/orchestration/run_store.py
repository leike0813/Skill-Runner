import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from server.config import config
from server.models import (
    CurrentRunProjection,
    InteractiveErrorCode,
    PendingOwner,
    ResumeCause,
    RunDispatchEnvelope,
    RunStateEnvelope,
    RunStatus,
)
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_interaction_history_entry,
    validate_pending_auth,
    validate_pending_auth_method_selection,
    validate_pending_interaction,
)
from server.services.platform import aiosqlite_compat as aiosqlite
from server.services.orchestration.run_store_auth_state_store import RunAuthStateStore
from server.services.orchestration.run_store_cache_store import RunCacheStore
from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.orchestration.run_store_interaction_store import RunInteractionStore, RunInteractiveRuntimeStore
from server.services.orchestration.run_store_request_store import RunRegistryStore, RunRequestStore
from server.services.orchestration.run_store_state_store import RunProjectionStateStore, RunRecoveryStateStore


class RunStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.RUNS_DB)
        self._database = RunStoreDatabase(self.db_path)
        self._request_store = RunRequestStore(self._database)
        self._run_registry = RunRegistryStore(self._database)
        self._cache_store = RunCacheStore(self._database)
        self._projection_state_store = RunProjectionStateStore(self._database)
        self._recovery_state_store = RunRecoveryStateStore(self._database)
        self._interactive_runtime_store = RunInteractiveRuntimeStore(self._database)
        self._interaction_store = RunInteractionStore(self._database)
        self._auth_state_store = RunAuthStateStore(self._database)

    def _connect(self):
        return self._database.connect()

    async def _ensure_initialized(self) -> None:
        await self._database.ensure_initialized()

    async def _init_db(self) -> None:
        await self._database.init_db()

    async def _migrate_interactive_runtime_table(self, conn: aiosqlite.Connection) -> None:
        await self._database._schema_migration.migrate_interactive_runtime_table(conn)

    async def create_request(
        self,
        request_id: str,
        skill_id: str,
        engine: str,
        parameter: Dict[str, Any],
        engine_options: Dict[str, Any],
        runtime_options: Dict[str, Any],
        effective_runtime_options: Optional[Dict[str, Any]] = None,
        client_metadata: Optional[Dict[str, Any]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        skill_source: str = "installed",
        request_upload_mode: str = "none",
        temp_skill_package_sha256: Optional[str] = None,
        temp_skill_manifest_id: Optional[str] = None,
        temp_skill_manifest_json: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._request_store.create_request(
            request_id=request_id,
            skill_id=skill_id,
            engine=engine,
            parameter=parameter,
            engine_options=engine_options,
            runtime_options=runtime_options,
            effective_runtime_options=effective_runtime_options,
            client_metadata=client_metadata,
            input_data=input_data,
            skill_source=skill_source,
            request_upload_mode=request_upload_mode,
            temp_skill_package_sha256=temp_skill_package_sha256,
            temp_skill_manifest_id=temp_skill_manifest_id,
            temp_skill_manifest_json=temp_skill_manifest_json,
        )

    async def update_request_manifest(
        self,
        request_id: str,
        manifest_path: str | None,
        manifest_hash: str,
        *,
        request_upload_mode: str | None = None,
    ) -> None:
        await self._request_store.update_request_manifest(
            request_id,
            manifest_path,
            manifest_hash,
            request_upload_mode=request_upload_mode,
        )

    async def update_request_effective_runtime_options(
        self,
        request_id: str,
        effective_runtime_options: Dict[str, Any],
    ) -> None:
        await self._request_store.update_request_effective_runtime_options(
            request_id,
            effective_runtime_options,
        )

    async def update_request_engine_options(
        self,
        request_id: str,
        engine_options: Dict[str, Any],
    ) -> None:
        await self._request_store.update_request_engine_options(request_id, engine_options)

    async def update_request_cache_key(self, request_id: str, cache_key: str, skill_fingerprint: str) -> None:
        await self._request_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)

    async def update_request_skill_identity(
        self,
        request_id: str,
        *,
        skill_id: str,
        temp_skill_manifest_id: str | None = None,
        temp_skill_manifest_json: Dict[str, Any] | None = None,
        temp_skill_package_sha256: str | None = None,
    ) -> None:
        await self._request_store.update_request_skill_identity(
            request_id,
            skill_id=skill_id,
            temp_skill_manifest_id=temp_skill_manifest_id,
            temp_skill_manifest_json=temp_skill_manifest_json,
            temp_skill_package_sha256=temp_skill_package_sha256,
        )

    async def update_request_run_id(self, request_id: str, run_id: str) -> None:
        await self._request_store.update_request_run_id(request_id, run_id)

    async def bind_request_run_id(self, request_id: str, run_id: str, *, status: str = "queued") -> None:
        await self._request_store.bind_request_run_id(request_id, run_id, status=status)

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._request_store.get_request(request_id)

    async def get_request_with_run(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._request_store.get_request_with_run(request_id)

    async def get_request_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        return await self._request_store.get_request_by_run_id(run_id)

    async def list_requests_with_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        return await self._request_store.list_requests_with_runs(limit=limit)

    async def count_requests_with_runs(self) -> int:
        return await self._request_store.count_requests_with_runs()

    async def list_requests_with_runs_page(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        return await self._request_store.list_requests_with_runs_page(page=page, page_size=page_size)

    async def create_run(
        self,
        run_id: str,
        cache_key: Optional[str],
        status: str,
        result_path: str = "",
        artifacts_manifest_path: str = "",
    ) -> None:
        await self._run_registry.create_run(
            run_id=run_id,
            cache_key=cache_key,
            status=status,
            result_path=result_path,
            artifacts_manifest_path=artifacts_manifest_path,
        )

    async def update_run_status(self, run_id: str, status: str, result_path: Optional[str] = None) -> None:
        await self._run_registry.update_run_status(run_id, status, result_path=result_path)

    async def set_current_projection(self, request_id: str, projection: Dict[str, Any]) -> None:
        await self._projection_state_store.set_current_projection(request_id, projection)

    async def set_run_state(self, request_id: str, state: Dict[str, Any]) -> None:
        await self._projection_state_store.set_run_state(request_id, state)

    async def get_run_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._projection_state_store.get_run_state(request_id)

    async def clear_run_state(self, request_id: str) -> None:
        await self._projection_state_store.clear_run_state(request_id)

    async def set_dispatch_state(self, request_id: str, state: Dict[str, Any]) -> None:
        await self._projection_state_store.set_dispatch_state(request_id, state)

    async def get_dispatch_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._projection_state_store.get_dispatch_state(request_id)

    async def clear_dispatch_state(self, request_id: str) -> None:
        await self._projection_state_store.clear_dispatch_state(request_id)

    async def get_current_projection(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._projection_state_store.get_current_projection(request_id)

    async def clear_current_projection(self, request_id: str) -> None:
        await self._projection_state_store.clear_current_projection(request_id)

    async def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._cache_store.record_cache_entry(cache_key, run_id)

    async def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._cache_store.record_temp_cache_entry(cache_key, run_id)

    async def _record_cache_entry(self, table: str, cache_key: str, run_id: str) -> None:
        await self._cache_store._record_cache_entry(table, cache_key, run_id)

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._cache_store.get_cached_run(cache_key)

    async def get_temp_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._cache_store.get_temp_cached_run(cache_key)

    async def get_cached_run_for_source(self, cache_key: str, source: str) -> Optional[str]:
        return await self._cache_store.get_cached_run_for_source(cache_key, source)

    async def _get_cached_run(self, table: str, cache_key: str) -> Optional[str]:
        return await self._cache_store._get_cached_run(table, cache_key)

    async def list_runs_for_cleanup(self, retention_days: int) -> List[Dict[str, Any]]:
        return await self._recovery_state_store.list_runs_for_cleanup(retention_days)

    async def delete_run_records(self, run_id: str) -> List[str]:
        return await self._recovery_state_store.delete_run_records(run_id)

    async def list_request_ids(self) -> List[str]:
        return await self._request_store.list_request_ids()

    async def clear_all(self) -> Dict[str, int]:
        return await self._recovery_state_store.clear_all()

    async def list_active_run_ids(self) -> List[str]:
        return await self._recovery_state_store.list_active_run_ids()

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return await self._run_registry.get_run(run_id)

    async def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        return await self._recovery_state_store.list_incomplete_runs()

    async def set_recovery_info(
        self,
        run_id: str,
        *,
        recovery_state: str,
        recovery_reason: Optional[str] = None,
        recovered_at: Optional[str] = None,
    ) -> None:
        await self._recovery_state_store.set_recovery_info(
            run_id,
            recovery_state=recovery_state,
            recovery_reason=recovery_reason,
            recovered_at=recovered_at,
        )

    async def get_recovery_info(self, run_id: str) -> Dict[str, Any]:
        return await self._recovery_state_store.get_recovery_info(run_id)

    async def set_cancel_requested(self, run_id: str, requested: bool = True) -> bool:
        return await self._recovery_state_store.set_cancel_requested(run_id, requested=requested)

    async def is_cancel_requested(self, run_id: str) -> bool:
        return await self._recovery_state_store.is_cancel_requested(run_id)

    async def _upsert_interactive_runtime(
        self,
        request_id: str,
        *,
        effective_session_timeout_sec: Optional[int] = None,
        session_handle_json: Optional[str] = None,
    ) -> None:
        await self._interactive_runtime_store._upsert_interactive_runtime(
            request_id,
            effective_session_timeout_sec=effective_session_timeout_sec,
            session_handle_json=session_handle_json,
        )

    async def set_interactive_profile(self, request_id: str, profile: Dict[str, Any]) -> None:
        await self._interactive_runtime_store.set_interactive_profile(request_id, profile)

    async def set_effective_session_timeout(self, request_id: str, timeout_sec: int) -> None:
        await self._interactive_runtime_store.set_effective_session_timeout(request_id, timeout_sec)

    async def get_interactive_profile(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._interactive_runtime_store.get_interactive_profile(request_id)

    async def get_effective_session_timeout(self, request_id: str) -> Optional[int]:
        return await self._interactive_runtime_store.get_effective_session_timeout(request_id)

    async def set_engine_session_handle(self, request_id: str, handle: Dict[str, Any]) -> None:
        await self._interactive_runtime_store.set_engine_session_handle(request_id, handle)

    async def get_engine_session_handle(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._interactive_runtime_store.get_engine_session_handle(request_id)

    async def clear_engine_session_handle(self, request_id: str) -> None:
        await self._interactive_runtime_store.clear_engine_session_handle(request_id)

    async def append_interaction_history(
        self,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: Dict[str, Any],
        *,
        source_attempt: int,
    ) -> None:
        await self._interaction_store.append_interaction_history(
            request_id=request_id,
            interaction_id=interaction_id,
            event_type=event_type,
            payload=payload,
            source_attempt=source_attempt,
        )

    async def issue_resume_ticket(
        self,
        request_id: str,
        *,
        cause: str,
        source_attempt: int,
        target_attempt: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self._auth_state_store.issue_resume_ticket(
            request_id,
            cause=cause,
            source_attempt=source_attempt,
            target_attempt=target_attempt,
            payload=payload,
        )

    async def get_resume_ticket(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._auth_state_store.get_resume_ticket(request_id)

    async def mark_resume_ticket_dispatched(self, request_id: str, ticket_id: str) -> bool:
        return await self._auth_state_store.mark_resume_ticket_dispatched(request_id, ticket_id)

    async def mark_resume_ticket_started(
        self,
        request_id: str,
        ticket_id: str,
        *,
        target_attempt: int,
    ) -> bool:
        return await self._auth_state_store.mark_resume_ticket_started(
            request_id,
            ticket_id,
            target_attempt=target_attempt,
        )

    async def clear_pending_interaction(self, request_id: str) -> None:
        await self._interaction_store.clear_pending_interaction(request_id)

    async def set_pending_auth(
        self,
        request_id: str,
        payload: Dict[str, Any],
        *,
        auth_resume_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._auth_state_store.set_pending_auth(
            request_id,
            payload,
            auth_resume_context=auth_resume_context,
        )

    async def set_pending_auth_method_selection(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._auth_state_store.set_pending_auth_method_selection(request_id, payload)

    async def get_pending_auth(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._auth_state_store.get_pending_auth(request_id)

    async def get_pending_auth_method_selection(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._auth_state_store.get_pending_auth_method_selection(request_id)

    async def clear_pending_auth(self, request_id: str) -> None:
        await self._auth_state_store.clear_pending_auth(request_id)

    async def clear_pending_auth_method_selection(self, request_id: str) -> None:
        await self._auth_state_store.clear_pending_auth_method_selection(request_id)

    async def set_auth_resume_context(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._auth_state_store.set_auth_resume_context(request_id, payload)

    async def get_auth_resume_context(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._auth_state_store.get_auth_resume_context(request_id)

    async def clear_auth_resume_context(self, request_id: str) -> None:
        await self._auth_state_store.clear_auth_resume_context(request_id)

    async def get_request_id_for_auth_session(self, auth_session_id: str) -> Optional[str]:
        return await self._auth_state_store.get_request_id_for_auth_session(auth_session_id)

    async def get_auth_session_status(self, request_id: str) -> Dict[str, Any]:
        return await self._auth_state_store.get_auth_session_status(request_id)

    async def list_interaction_history(self, request_id: str) -> List[Dict[str, Any]]:
        return await self._interaction_store.list_interaction_history(request_id)

    async def set_pending_interaction(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._interaction_store.set_pending_interaction(request_id, payload)

    async def get_pending_interaction(self, request_id: str) -> Optional[Dict[str, Any]]:
        return await self._interaction_store.get_pending_interaction(request_id)

    async def get_interaction_count(self, request_id: str) -> int:
        return await self._interaction_store.get_interaction_count(request_id)

    async def get_auto_decision_stats(self, request_id: str) -> Dict[str, Any]:
        return await self._interaction_store.get_auto_decision_stats(request_id)

    async def get_interaction_reply(
        self, request_id: str, interaction_id: int, idempotency_key: str
    ) -> Optional[Any]:
        return await self._interaction_store.get_interaction_reply(request_id, interaction_id, idempotency_key)

    async def consume_interaction_reply(self, request_id: str, interaction_id: int) -> Optional[Any]:
        return await self._interaction_store.consume_interaction_reply(request_id, interaction_id)

    async def submit_interaction_reply(
        self,
        request_id: str,
        interaction_id: int,
        response: Any,
        idempotency_key: Optional[str],
    ) -> str:
        return await self._interaction_store.submit_interaction_reply(
            request_id,
            interaction_id,
            response,
            idempotency_key,
        )

    def _resume_ticket_from_row(self, row: aiosqlite.Row) -> Dict[str, Any]:
        return self._auth_state_store._resume_ticket_from_row(row)


run_store = RunStore()
logger = logging.getLogger(__name__)
