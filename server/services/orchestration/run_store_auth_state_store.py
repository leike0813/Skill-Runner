import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from server.models import InteractiveErrorCode
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_pending_auth,
    validate_pending_auth_method_selection,
)
from server.services.engine_management.engine_auth_flow_manager import engine_auth_flow_manager
from server.services.platform import aiosqlite_compat as aiosqlite

from .auth_session_durable_store import (
    DURABLE_AUTH_SESSION_ACTIVE_STATUSES,
    DURABLE_AUTH_SESSION_TABLE,
    build_auth_session_scope_key,
)
from .run_store_database import RunStoreDatabase

logger = logging.getLogger(__name__)


class RunAuthStateStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def issue_resume_ticket(
        self,
        request_id: str,
        *,
        cause: str,
        source_attempt: int,
        target_attempt: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT ticket_id, cause, source_attempt, target_attempt, payload_json, state,
                       created_at, dispatched_at, started_at, updated_at
                FROM request_resume_tickets
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
            if row is not None:
                existing = self._resume_ticket_from_row(row)
                if (
                    existing["cause"] == cause
                    and int(existing["source_attempt"]) == int(source_attempt)
                    and int(existing["target_attempt"]) == int(target_attempt)
                ):
                    return existing
            now = datetime.utcnow().isoformat()
            ticket = {
                "ticket_id": str(uuid4()),
                "cause": cause,
                "source_attempt": int(source_attempt),
                "target_attempt": int(target_attempt),
                "payload": payload,
                "state": "issued",
                "created_at": now,
                "dispatched_at": None,
                "started_at": None,
                "updated_at": now,
            }
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_resume_tickets (
                    request_id, ticket_id, cause, source_attempt, target_attempt,
                    payload_json, state, created_at, dispatched_at, started_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    ticket["ticket_id"],
                    ticket["cause"],
                    ticket["source_attempt"],
                    ticket["target_attempt"],
                    json.dumps(payload, sort_keys=True) if payload is not None else None,
                    ticket["state"],
                    ticket["created_at"],
                    ticket["dispatched_at"],
                    ticket["started_at"],
                    ticket["updated_at"],
                ),
            )
            await conn.commit()
        return ticket

    async def get_resume_ticket(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT ticket_id, cause, source_attempt, target_attempt, payload_json, state,
                       created_at, dispatched_at, started_at, updated_at
                FROM request_resume_tickets
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._resume_ticket_from_row(row)

    async def mark_resume_ticket_dispatched(self, request_id: str, ticket_id: str) -> bool:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                UPDATE request_resume_tickets
                SET state = 'dispatched', dispatched_at = ?, updated_at = ?
                WHERE request_id = ? AND ticket_id = ? AND state = 'issued'
                """,
                (now, now, request_id, ticket_id),
            )
            await conn.commit()
        return int(cursor.rowcount or 0) > 0

    async def mark_resume_ticket_started(
        self,
        request_id: str,
        ticket_id: str,
        *,
        target_attempt: int,
    ) -> bool:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                UPDATE request_resume_tickets
                SET state = 'started', started_at = ?, updated_at = ?
                WHERE request_id = ?
                  AND ticket_id = ?
                  AND target_attempt = ?
                  AND state IN ('issued', 'dispatched')
                """,
                (now, now, request_id, ticket_id, int(target_attempt)),
            )
            await conn.commit()
        return int(cursor.rowcount or 0) > 0

    async def set_pending_auth(
        self,
        request_id: str,
        payload: Dict[str, Any],
        *,
        auth_resume_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._database.ensure_initialized()
        try:
            validate_pending_auth(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_auth_sessions (
                    request_id, auth_session_id, payload_json, state,
                    submission_kind, submission_redacted_json, auth_resume_context_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    str(payload["auth_session_id"]),
                    json.dumps(payload, sort_keys=True),
                    "pending",
                    None,
                    None,
                    json.dumps(auth_resume_context, sort_keys=True)
                    if auth_resume_context is not None
                    else None,
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def set_pending_auth_method_selection(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        try:
            validate_pending_auth_method_selection(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_auth_method_selection (
                    request_id, payload_json, state, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    json.dumps(payload, sort_keys=True),
                    "pending",
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def upsert_durable_auth_session(
        self,
        *,
        auth_session_id: str,
        engine: str,
        provider_id: str | None,
        request_id: str | None,
        run_id: str | None,
        source_attempt: int | None,
        status: str,
        payload: Dict[str, Any],
        auth_method: str | None = None,
        challenge_kind: str | None = None,
        driver: str | None = None,
        execution_mode: str | None = None,
        transport: str | None = None,
        input_kind: str | None = None,
        expires_at: str | None = None,
        last_error: str | None = None,
        resume_ticket_id: str | None = None,
        terminal_reason: str | None = None,
    ) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat() + "Z"
        created_at = str(payload.get("created_at") or now)
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"""
                INSERT OR REPLACE INTO {DURABLE_AUTH_SESSION_TABLE} (
                    auth_session_id, engine, provider_id, scope_key, request_id, run_id,
                    source_attempt, status, auth_method, challenge_kind, driver,
                    execution_mode, transport, input_kind, created_at, updated_at,
                    expires_at, last_error, resume_ticket_id, terminal_reason, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    auth_session_id,
                    engine,
                    provider_id,
                    build_auth_session_scope_key(engine, provider_id),
                    request_id,
                    run_id,
                    int(source_attempt) if source_attempt is not None else None,
                    status,
                    auth_method,
                    challenge_kind,
                    driver,
                    execution_mode,
                    transport,
                    input_kind,
                    created_at,
                    now,
                    expires_at,
                    last_error,
                    resume_ticket_id,
                    terminal_reason,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            await conn.commit()

    async def get_durable_auth_session(self, auth_session_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT * FROM {DURABLE_AUTH_SESSION_TABLE} WHERE auth_session_id = ? LIMIT 1",
                (auth_session_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._durable_auth_session_from_row(row)

    async def get_active_durable_auth_session_for_scope(
        self,
        *,
        engine: str,
        provider_id: str | None,
    ) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        placeholders = ",".join("?" for _ in DURABLE_AUTH_SESSION_ACTIVE_STATUSES)
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"""
                SELECT *
                FROM {DURABLE_AUTH_SESSION_TABLE}
                WHERE scope_key = ? AND status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (build_auth_session_scope_key(engine, provider_id), *DURABLE_AUTH_SESSION_ACTIVE_STATUSES),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._durable_auth_session_from_row(row)

    async def list_active_durable_auth_sessions_for_request(self, request_id: str) -> list[Dict[str, Any]]:
        await self._database.ensure_initialized()
        placeholders = ",".join("?" for _ in DURABLE_AUTH_SESSION_ACTIVE_STATUSES)
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"""
                SELECT *
                FROM {DURABLE_AUTH_SESSION_TABLE}
                WHERE request_id = ? AND status IN ({placeholders})
                ORDER BY updated_at DESC
                """,
                (request_id, *DURABLE_AUTH_SESSION_ACTIVE_STATUSES),
            )
            rows = await cursor.fetchall()
        return [self._durable_auth_session_from_row(row) for row in rows]

    async def mark_durable_auth_session_terminal(
        self,
        auth_session_id: str,
        *,
        status: str,
        last_error: str | None = None,
        terminal_reason: str | None = None,
    ) -> None:
        existing = await self.get_durable_auth_session(auth_session_id)
        if existing is None:
            return
        payload = dict(existing.get("payload") or {})
        payload["status"] = status
        if last_error is not None:
            payload["error"] = last_error
        if terminal_reason is not None:
            payload["terminal_reason"] = terminal_reason
        await self.upsert_durable_auth_session(
            auth_session_id=auth_session_id,
            engine=str(existing.get("engine") or ""),
            provider_id=existing.get("provider_id"),
            request_id=existing.get("request_id"),
            run_id=existing.get("run_id"),
            source_attempt=existing.get("source_attempt"),
            status=status,
            payload=payload,
            auth_method=existing.get("auth_method"),
            challenge_kind=existing.get("challenge_kind"),
            driver=existing.get("driver"),
            execution_mode=existing.get("execution_mode"),
            transport=existing.get("transport"),
            input_kind=existing.get("input_kind"),
            expires_at=existing.get("expires_at"),
            last_error=last_error if last_error is not None else existing.get("last_error"),
            resume_ticket_id=existing.get("resume_ticket_id"),
            terminal_reason=terminal_reason if terminal_reason is not None else existing.get("terminal_reason"),
        )

    async def get_pending_auth(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_auth_sessions
                WHERE request_id = ? AND state = 'pending'
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
            logger.warning("Invalid pending auth JSON ignored: request_id=%s", request_id)
            return None
        try:
            validate_pending_auth(payload)
        except ProtocolSchemaViolation as exc:
            logger.warning(
                "Invalid pending auth payload ignored: request_id=%s detail=%s",
                request_id,
                str(exc),
            )
            return None
        return payload

    async def get_pending_auth_method_selection(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_auth_method_selection
                WHERE request_id = ? AND state = 'pending'
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
            logger.warning("Invalid pending auth method selection JSON ignored: request_id=%s", request_id)
            return None
        try:
            validate_pending_auth_method_selection(payload)
        except ProtocolSchemaViolation as exc:
            logger.warning(
                "Invalid pending auth method selection payload ignored: request_id=%s detail=%s",
                request_id,
                str(exc),
            )
            return None
        return payload

    async def clear_pending_auth(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_auth_sessions
                SET state = 'consumed', updated_at = ?
                WHERE request_id = ? AND state = 'pending'
                """,
                (now, request_id),
            )
            await conn.commit()

    async def clear_pending_auth_method_selection(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_auth_method_selection
                SET state = 'consumed', updated_at = ?
                WHERE request_id = ? AND state = 'pending'
                """,
                (now, request_id),
            )
            await conn.commit()

    async def set_auth_resume_context(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_auth_sessions
                SET auth_resume_context_json = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (json.dumps(payload, sort_keys=True), now, request_id),
            )
            await conn.commit()

    async def get_auth_resume_context(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT auth_resume_context_json
                FROM request_auth_sessions
                WHERE request_id = ?
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row or row["auth_resume_context_json"] is None:
            return None
        try:
            return json.loads(row["auth_resume_context_json"])
        except (json.JSONDecodeError, TypeError):
            return None

    async def clear_auth_resume_context(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_auth_sessions
                SET auth_resume_context_json = NULL, updated_at = ?
                WHERE request_id = ?
                """,
                (now, request_id),
            )
            await conn.commit()

    async def get_request_id_for_auth_session(self, auth_session_id: str) -> Optional[str]:
        await self._database.ensure_initialized()
        durable = await self.get_durable_auth_session(auth_session_id)
        if durable is not None and isinstance(durable.get("request_id"), str):
            return str(durable["request_id"])
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT request_id
                FROM request_auth_sessions
                WHERE auth_session_id = ?
                LIMIT 1
                """,
                (auth_session_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return str(row["request_id"])

    async def get_auth_session_status(self, request_id: str) -> Dict[str, Any]:
        pending_selection = await self.get_pending_auth_method_selection(request_id)
        pending_auth = await self.get_pending_auth(request_id)
        resume_ticket = await self.get_resume_ticket(request_id)
        server_now = datetime.utcnow().isoformat() + "Z"
        waiting_auth = pending_selection is not None or pending_auth is not None
        if pending_auth is not None:
            auth_session_id = pending_auth.get("auth_session_id")
            snapshot = None
            durable = None
            if isinstance(auth_session_id, str) and auth_session_id:
                durable = await self.get_durable_auth_session(auth_session_id)
                try:
                    snapshot = engine_auth_flow_manager.get_session(auth_session_id)
                except KeyError:
                    snapshot = None
            created_at = (
                snapshot.get("created_at")
                if isinstance(snapshot, dict) and isinstance(snapshot.get("created_at"), str)
                else (
                    durable.get("created_at")
                    if isinstance(durable, dict) and isinstance(durable.get("created_at"), str)
                    else pending_auth.get("created_at")
                )
            )
            expires_at = (
                snapshot.get("expires_at")
                if isinstance(snapshot, dict) and isinstance(snapshot.get("expires_at"), str)
                else (
                    durable.get("expires_at")
                    if isinstance(durable, dict) and isinstance(durable.get("expires_at"), str)
                    else pending_auth.get("expires_at")
                )
            )
            timed_out = False
            status_obj = (
                snapshot.get("status")
                if isinstance(snapshot, dict)
                else (durable.get("status") if isinstance(durable, dict) else None)
            )
            if status_obj == "expired":
                timed_out = True
            else:
                expires_at_dt = None
                if isinstance(expires_at, str) and expires_at:
                    try:
                        expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    except ValueError:
                        expires_at_dt = None
                if expires_at_dt is not None:
                    timed_out = expires_at_dt <= datetime.utcnow().astimezone(expires_at_dt.tzinfo)
            timeout_sec = pending_auth.get("timeout_sec")
            if timeout_sec is None and isinstance(created_at, str) and isinstance(expires_at, str):
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    delta = int((expires_dt - created_dt).total_seconds())
                    timeout_sec = delta if delta > 0 else None
                except ValueError:
                    timeout_sec = None
            return {
                "waiting_auth": waiting_auth,
                "phase": "challenge_active",
                "timed_out": timed_out,
                "pending_owner": "waiting_auth.challenge_active",
                "available_methods": pending_selection.get("available_methods", []) if isinstance(pending_selection, dict) else (
                    [pending_auth.get("auth_method")] if pending_auth.get("auth_method") else []
                ),
                "selected_method": pending_auth.get("auth_method"),
                "auth_session_id": auth_session_id,
                "challenge_kind": pending_auth.get("challenge_kind"),
                "timeout_sec": timeout_sec,
                "created_at": created_at,
                "expires_at": expires_at,
                "server_now": server_now,
                "last_error": (
                    snapshot.get("error")
                    if isinstance(snapshot, dict) and isinstance(snapshot.get("error"), str)
                    else (
                        durable.get("last_error")
                        if isinstance(durable, dict) and isinstance(durable.get("last_error"), str)
                        else pending_auth.get("last_error")
                    )
                ),
                "provider_id": pending_auth.get("provider_id"),
                "transport": (
                    snapshot.get("transport")
                    if isinstance(snapshot, dict) and isinstance(snapshot.get("transport"), str)
                    else (durable.get("transport") if isinstance(durable, dict) else None)
                ),
                "session_status": status_obj,
                "source_attempt": pending_auth.get("source_attempt"),
                "target_attempt": (
                    resume_ticket.get("target_attempt") if isinstance(resume_ticket, dict) else None
                ),
                "resume_ticket_id": (
                    resume_ticket.get("ticket_id") if isinstance(resume_ticket, dict) else None
                ),
                "ticket_consumed": bool(
                    isinstance(resume_ticket, dict)
                    and resume_ticket.get("state") in {"dispatched", "started"}
                ),
                "pending_auth_method_selection": pending_selection,
                "pending_auth": pending_auth,
            }
        if pending_selection is not None:
            return {
                "waiting_auth": waiting_auth,
                "phase": "method_selection",
                "timed_out": False,
                "pending_owner": "waiting_auth.method_selection",
                "available_methods": pending_selection.get("available_methods", []),
                "selected_method": None,
                "auth_session_id": None,
                "challenge_kind": None,
                "timeout_sec": None,
                "created_at": None,
                "expires_at": None,
                "server_now": server_now,
                "last_error": pending_selection.get("last_error"),
                "source_attempt": pending_selection.get("source_attempt"),
                "target_attempt": (
                    resume_ticket.get("target_attempt") if isinstance(resume_ticket, dict) else None
                ),
                "resume_ticket_id": (
                    resume_ticket.get("ticket_id") if isinstance(resume_ticket, dict) else None
                ),
                "ticket_consumed": bool(
                    isinstance(resume_ticket, dict)
                    and resume_ticket.get("state") in {"dispatched", "started"}
                ),
                "pending_auth_method_selection": pending_selection,
                "pending_auth": None,
            }
        return {
            "waiting_auth": False,
            "phase": None,
            "timed_out": False,
            "pending_owner": None,
            "available_methods": [],
            "selected_method": None,
            "auth_session_id": None,
            "challenge_kind": None,
            "timeout_sec": None,
            "created_at": None,
            "expires_at": None,
            "server_now": server_now,
            "last_error": None,
            "source_attempt": None,
            "target_attempt": (
                resume_ticket.get("target_attempt") if isinstance(resume_ticket, dict) else None
            ),
            "resume_ticket_id": (
                resume_ticket.get("ticket_id") if isinstance(resume_ticket, dict) else None
            ),
            "ticket_consumed": bool(
                isinstance(resume_ticket, dict)
                and resume_ticket.get("state") in {"dispatched", "started"}
            ),
            "pending_auth_method_selection": None,
            "pending_auth": None,
        }

    def _resume_ticket_from_row(self, row: aiosqlite.Row) -> Dict[str, Any]:
        payload_json = row["payload_json"]
        payload: Optional[Dict[str, Any]] = None
        if isinstance(payload_json, str) and payload_json:
            try:
                payload_obj = json.loads(payload_json)
            except (json.JSONDecodeError, TypeError):
                payload_obj = None
            if isinstance(payload_obj, dict):
                payload = payload_obj
        return {
            "ticket_id": str(row["ticket_id"]),
            "cause": str(row["cause"]),
            "source_attempt": int(row["source_attempt"]),
            "target_attempt": int(row["target_attempt"]),
            "payload": payload,
            "state": str(row["state"]),
            "created_at": str(row["created_at"]),
            "dispatched_at": row["dispatched_at"],
            "started_at": row["started_at"],
            "updated_at": str(row["updated_at"]),
        }

    def _durable_auth_session_from_row(self, row: aiosqlite.Row) -> Dict[str, Any]:
        payload_raw = row["payload_json"]
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return {
            "auth_session_id": row["auth_session_id"],
            "engine": row["engine"],
            "provider_id": row["provider_id"],
            "scope_key": row["scope_key"],
            "request_id": row["request_id"],
            "run_id": row["run_id"],
            "source_attempt": row["source_attempt"],
            "status": row["status"],
            "auth_method": row["auth_method"],
            "challenge_kind": row["challenge_kind"],
            "driver": row["driver"],
            "execution_mode": row["execution_mode"],
            "transport": row["transport"],
            "input_kind": row["input_kind"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"],
            "last_error": row["last_error"],
            "resume_ticket_id": row["resume_ticket_id"],
            "terminal_reason": row["terminal_reason"],
            "payload": payload,
        }
