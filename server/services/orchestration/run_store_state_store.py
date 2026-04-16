import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from server.models import CurrentRunProjection, PendingOwner, ResumeCause, RunDispatchEnvelope, RunStateEnvelope, RunStatus
from server.services.platform import aiosqlite_compat as aiosqlite

from .auth_session_durable_store import DURABLE_AUTH_SESSION_TABLE
from .run_store_database import RunStoreDatabase

logger = logging.getLogger(__name__)


class RunProjectionStateStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def set_current_projection(self, request_id: str, projection: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        model = CurrentRunProjection.model_validate(projection)
        payload = model.model_dump(mode="json")
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_current_projection (
                    request_id, run_id, status, current_attempt, pending_owner,
                    pending_interaction_id, pending_auth_session_id, resume_ticket_id,
                    resume_cause, source_attempt, target_attempt, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    model.run_id,
                    model.status.value,
                    model.current_attempt,
                    model.pending_owner.value if isinstance(model.pending_owner, PendingOwner) else None,
                    model.pending_interaction_id,
                    model.pending_auth_session_id,
                    model.resume_ticket_id,
                    model.resume_cause.value if isinstance(model.resume_cause, ResumeCause) else None,
                    model.source_attempt,
                    model.target_attempt,
                    json.dumps(payload, sort_keys=True),
                    model.updated_at.isoformat(),
                ),
            )
            await conn.commit()

    async def set_run_state(self, request_id: str, state: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        model = RunStateEnvelope.model_validate(state)
        payload = model.model_dump(mode="json")
        pending_owner_obj = payload.get("pending", {}).get("owner")
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_run_state (
                    request_id, run_id, status, current_attempt, pending_owner, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    model.run_id,
                    model.status.value,
                    model.current_attempt,
                    pending_owner_obj,
                    json.dumps(payload, sort_keys=True),
                    model.updated_at.isoformat(),
                ),
            )
            await conn.commit()

    async def get_run_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_run_state
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid run state JSON ignored: request_id=%s", request_id)
            return None
        try:
            return RunStateEnvelope.model_validate(payload).model_dump(mode="json")
        except ValidationError:
            logger.warning("Invalid run state payload ignored: request_id=%s", request_id, exc_info=True)
            return None

    async def clear_run_state(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("DELETE FROM request_run_state WHERE request_id = ?", (request_id,))
            await conn.commit()

    async def set_dispatch_state(self, request_id: str, state: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        model = RunDispatchEnvelope.model_validate(state)
        payload = model.model_dump(mode="json")
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_dispatch_state (
                    request_id, run_id, dispatch_ticket_id, phase, worker_claim_id, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    model.run_id,
                    model.dispatch_ticket_id,
                    model.phase.value,
                    model.worker_claim_id,
                    json.dumps(payload, sort_keys=True),
                    model.updated_at.isoformat(),
                ),
            )
            await conn.commit()

    async def get_dispatch_state(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_dispatch_state
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid dispatch state JSON ignored: request_id=%s", request_id)
            return None
        try:
            return RunDispatchEnvelope.model_validate(payload).model_dump(mode="json")
        except ValidationError:
            logger.warning("Invalid dispatch state payload ignored: request_id=%s", request_id, exc_info=True)
            return None

    async def clear_dispatch_state(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("DELETE FROM request_dispatch_state WHERE request_id = ?", (request_id,))
            await conn.commit()

    async def get_current_projection(self, request_id: str) -> Optional[Dict[str, Any]]:
        state_payload = await self.get_run_state(request_id)
        if isinstance(state_payload, dict):
            pending_obj = state_payload.get("pending")
            resume_obj = state_payload.get("resume")
            runtime_obj = state_payload.get("runtime")
            pending: Dict[str, Any] = pending_obj if isinstance(pending_obj, dict) else {}
            resume: Dict[str, Any] = resume_obj if isinstance(resume_obj, dict) else {}
            runtime: Dict[str, Any] = runtime_obj if isinstance(runtime_obj, dict) else {}
            updated_at_raw = state_payload.get("updated_at")
            updated_at: datetime | None = updated_at_raw if isinstance(updated_at_raw, datetime) else None
            if updated_at is None and isinstance(updated_at_raw, str) and updated_at_raw:
                try:
                    updated_at = datetime.fromisoformat(updated_at_raw)
                except ValueError:
                    updated_at = None
            if updated_at is None:
                updated_at = datetime.utcnow()
            try:
                projection = CurrentRunProjection(
                    request_id=str(state_payload.get("request_id") or ""),
                    run_id=str(state_payload.get("run_id") or ""),
                    status=state_payload.get("status", RunStatus.QUEUED.value),
                    updated_at=updated_at,
                    current_attempt=int(state_payload.get("current_attempt") or 1),
                    pending_owner=pending.get("owner"),
                    pending_interaction_id=pending.get("interaction_id"),
                    pending_auth_session_id=pending.get("auth_session_id"),
                    resume_ticket_id=resume.get("resume_ticket_id"),
                    resume_cause=resume.get("resume_cause"),
                    source_attempt=resume.get("source_attempt"),
                    target_attempt=resume.get("target_attempt"),
                    conversation_mode=runtime.get("conversation_mode"),
                    requested_execution_mode=runtime.get("requested_execution_mode"),
                    effective_execution_mode=runtime.get("effective_execution_mode"),
                    effective_interactive_require_user_reply=runtime.get("effective_interactive_require_user_reply"),
                    effective_interactive_reply_timeout_sec=runtime.get("effective_interactive_reply_timeout_sec"),
                    effective_session_timeout_sec=runtime.get("effective_session_timeout_sec"),
                    error=state_payload.get("error"),
                    warnings=list(state_payload.get("warnings") or []),
                )
                return projection.model_dump(mode="json")
            except (TypeError, ValueError, ValidationError):
                logger.warning(
                    "Failed to convert run state into current projection: request_id=%s",
                    request_id,
                    exc_info=True,
                )
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_current_projection
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid current projection JSON ignored: request_id=%s", request_id)
            return None
        try:
            return CurrentRunProjection.model_validate(payload).model_dump(mode="json")
        except ValidationError:
            logger.warning("Invalid current projection payload ignored: request_id=%s", request_id, exc_info=True)
            return None

    async def clear_current_projection(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("DELETE FROM request_current_projection WHERE request_id = ?", (request_id,))
            await conn.commit()


class RunRecoveryStateStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def list_runs_for_cleanup(self, retention_days: int) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        if retention_days <= 0:
            return []
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        candidates = []
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT run_id, status, created_at FROM runs")
            rows = await cursor.fetchall()
        for row in rows:
            status = row["status"]
            if status in ("running", "queued", "waiting_user", "waiting_auth"):
                continue
            if status == "failed":
                candidates.append(dict(row))
                continue
            created_at = row["created_at"]
            try:
                created_ts = datetime.fromisoformat(created_at)
            except ValueError:
                candidates.append(dict(row))
                continue
            if created_ts <= cutoff:
                candidates.append(dict(row))
        return candidates

    async def delete_run_records(self, run_id: str) -> List[str]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            request_cur = await conn.execute("SELECT request_id FROM requests WHERE run_id = ?", (run_id,))
            request_rows = await request_cur.fetchall()
            request_ids = [row["request_id"] for row in request_rows]
            if request_ids:
                placeholders = ",".join("?" for _ in request_ids)
                await conn.execute(
                    f"DELETE FROM request_interactions WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_interactive_runtime WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_interaction_history WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_auth_sessions WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_auth_method_selection WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM {DURABLE_AUTH_SESSION_TABLE} WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_current_projection WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_run_state WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_dispatch_state WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
            await conn.execute("DELETE FROM requests WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM temp_cache_entries WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            await conn.commit()
        return request_ids

    async def clear_all(self) -> Dict[str, int]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            run_rows_cur = await conn.execute("SELECT run_id FROM runs")
            request_rows_cur = await conn.execute("SELECT request_id FROM requests")
            cache_rows_cur = await conn.execute("SELECT cache_key FROM cache_entries")
            temp_cache_rows_cur = await conn.execute("SELECT cache_key FROM temp_cache_entries")
            run_rows = await run_rows_cur.fetchall()
            request_rows = await request_rows_cur.fetchall()
            cache_rows = await cache_rows_cur.fetchall()
            temp_cache_rows = await temp_cache_rows_cur.fetchall()
            run_count = len(run_rows)
            request_count = len(request_rows)
            cache_count = len(cache_rows) + len(temp_cache_rows)
            await conn.execute("DELETE FROM request_interactions")
            await conn.execute("DELETE FROM request_interactive_runtime")
            await conn.execute("DELETE FROM request_interaction_history")
            await conn.execute("DELETE FROM request_auth_sessions")
            await conn.execute("DELETE FROM request_auth_method_selection")
            await conn.execute(f"DELETE FROM {DURABLE_AUTH_SESSION_TABLE}")
            await conn.execute("DELETE FROM request_resume_tickets")
            await conn.execute("DELETE FROM request_current_projection")
            await conn.execute("DELETE FROM request_run_state")
            await conn.execute("DELETE FROM request_dispatch_state")
            await conn.execute("DELETE FROM cache_entries")
            await conn.execute("DELETE FROM temp_cache_entries")
            await conn.execute("DELETE FROM runs")
            await conn.execute("DELETE FROM requests")
            await conn.commit()
        return {"runs": run_count, "requests": request_count, "cache_entries": cache_count}

    async def list_active_run_ids(self) -> List[str]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?, ?, ?)",
                ("queued", "running", "waiting_user", "waiting_auth"),
            )
            rows = await cursor.fetchall()
        return [row["run_id"] for row in rows if row["run_id"]]

    async def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.run_id AS run_id,
                    req.skill_id AS skill_id,
                    req.engine AS engine,
                    req.runtime_options_json AS runtime_options_json,
                    run.status AS run_status,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason,
                    ir.effective_session_timeout_sec AS effective_session_timeout_sec,
                    ir.session_handle_json AS session_handle_json,
                    ir.updated_at AS interactive_runtime_updated_at,
                    auth.payload_json AS pending_auth_json,
                    auth.auth_session_id AS auth_session_id,
                    auth.auth_resume_context_json AS auth_resume_context_json,
                    auth_select.payload_json AS pending_auth_method_selection_json
                FROM requests req
                JOIN runs run ON req.run_id = run.run_id
                LEFT JOIN request_interactive_runtime ir ON req.request_id = ir.request_id
                LEFT JOIN request_auth_sessions auth ON req.request_id = auth.request_id
                LEFT JOIN request_auth_method_selection auth_select ON req.request_id = auth_select.request_id
                WHERE run.status IN ('queued', 'running', 'waiting_user', 'waiting_auth')
                ORDER BY req.created_at ASC
                """
            )
            rows = await cursor.fetchall()
        records: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            runtime_options_json = item.pop("runtime_options_json", "{}")
            session_handle_json = item.pop("session_handle_json", None)
            pending_auth_json = item.pop("pending_auth_json", None)
            auth_resume_context_json = item.pop("auth_resume_context_json", None)
            pending_auth_method_selection_json = item.pop("pending_auth_method_selection_json", None)
            timeout_obj = item.get("effective_session_timeout_sec")
            try:
                item["runtime_options"] = json.loads(runtime_options_json or "{}")
            except (json.JSONDecodeError, TypeError):
                item["runtime_options"] = {}
            if timeout_obj is None:
                item["interactive_session_config"] = None
            else:
                try:
                    item["interactive_session_config"] = {"session_timeout_sec": int(timeout_obj)}
                except (TypeError, ValueError, OverflowError):
                    item["interactive_session_config"] = None
            try:
                item["session_handle"] = json.loads(session_handle_json) if session_handle_json else None
            except (json.JSONDecodeError, TypeError):
                item["session_handle"] = None
            try:
                item["pending_auth"] = json.loads(pending_auth_json) if pending_auth_json else None
            except (json.JSONDecodeError, TypeError):
                item["pending_auth"] = None
            try:
                item["auth_resume_context"] = (
                    json.loads(auth_resume_context_json) if auth_resume_context_json else None
                )
            except (json.JSONDecodeError, TypeError):
                item["auth_resume_context"] = None
            try:
                item["pending_auth_method_selection"] = (
                    json.loads(pending_auth_method_selection_json)
                    if pending_auth_method_selection_json
                    else None
                )
            except (json.JSONDecodeError, TypeError):
                item["pending_auth_method_selection"] = None
            records.append(item)
        return records

    async def set_recovery_info(
        self,
        run_id: str,
        *,
        recovery_state: str,
        recovery_reason: Optional[str] = None,
        recovered_at: Optional[str] = None,
    ) -> None:
        await self._database.ensure_initialized()
        recovered_ts = recovered_at or datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE runs
                SET recovery_state = ?, recovered_at = ?, recovery_reason = ?
                WHERE run_id = ?
                """,
                (recovery_state, recovered_ts, recovery_reason, run_id),
            )
            await conn.commit()

    async def get_recovery_info(self, run_id: str) -> Dict[str, Any]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT recovery_state, recovered_at, recovery_reason
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return {
                "recovery_state": "none",
                "recovered_at": None,
                "recovery_reason": None,
            }
        return {
            "recovery_state": row["recovery_state"] or "none",
            "recovered_at": row["recovered_at"],
            "recovery_reason": row["recovery_reason"],
        }

    async def set_cancel_requested(self, run_id: str, requested: bool = True) -> bool:
        await self._database.ensure_initialized()
        next_value = 1 if requested else 0
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT cancel_requested FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            current_value = int(row["cancel_requested"] or 0)
            await conn.execute("UPDATE runs SET cancel_requested = ? WHERE run_id = ?", (next_value, run_id))
            await conn.commit()
        return current_value != next_value

    async def is_cancel_requested(self, run_id: str) -> bool:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT cancel_requested FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return False
        return int(row["cancel_requested"] or 0) == 1
