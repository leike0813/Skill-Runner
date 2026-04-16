import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from server.config import config
from server.models import InteractiveErrorCode
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_interaction_history_entry,
    validate_pending_interaction,
)
from server.services.platform import aiosqlite_compat as aiosqlite

from .run_store_database import RunStoreDatabase

logger = logging.getLogger(__name__)


class RunInteractiveRuntimeStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def _upsert_interactive_runtime(
        self,
        request_id: str,
        *,
        effective_session_timeout_sec: Optional[int] = None,
        session_handle_json: Optional[str] = None,
    ) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT effective_session_timeout_sec, session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
            current = dict(row) if row else {}
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactive_runtime (
                    request_id, effective_session_timeout_sec, session_handle_json, updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    request_id,
                    (
                        effective_session_timeout_sec
                        if effective_session_timeout_sec is not None
                        else current.get("effective_session_timeout_sec")
                    ),
                    session_handle_json
                    if session_handle_json is not None
                    else current.get("session_handle_json"),
                    now,
                ),
            )
            await conn.commit()

    async def set_interactive_profile(self, request_id: str, profile: Dict[str, Any]) -> None:
        timeout = profile.get("session_timeout_sec")
        if timeout is None:
            timeout = config.SYSTEM.SESSION_TIMEOUT_SEC
        await self._upsert_interactive_runtime(request_id, effective_session_timeout_sec=int(timeout))

    async def set_effective_session_timeout(self, request_id: str, timeout_sec: int) -> None:
        await self._upsert_interactive_runtime(
            request_id,
            effective_session_timeout_sec=int(timeout_sec),
        )

    async def get_interactive_profile(self, request_id: str) -> Optional[Dict[str, Any]]:
        timeout = await self.get_effective_session_timeout(request_id)
        if timeout is None:
            return None
        return {"session_timeout_sec": int(timeout)}

    async def get_effective_session_timeout(self, request_id: str) -> Optional[int]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT effective_session_timeout_sec
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row or row["effective_session_timeout_sec"] is None:
            return None
        return int(row["effective_session_timeout_sec"])

    async def set_engine_session_handle(self, request_id: str, handle: Dict[str, Any]) -> None:
        await self._upsert_interactive_runtime(
            request_id,
            session_handle_json=json.dumps(handle, sort_keys=True),
        )

    async def get_engine_session_handle(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row or row["session_handle_json"] is None:
            return None
        return json.loads(row["session_handle_json"])

    async def clear_engine_session_handle(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_interactive_runtime
                SET session_handle_json = NULL, updated_at = ?
                WHERE request_id = ?
                """,
                (now, request_id),
            )
            await conn.commit()


class RunInteractionStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def append_interaction_history(
        self,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: Dict[str, Any],
        *,
        source_attempt: int,
    ) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        history_payload = dict(payload)
        history_payload.setdefault("source_attempt", int(source_attempt))
        entry = {
            "interaction_id": int(interaction_id),
            "source_attempt": int(source_attempt),
            "event_type": event_type,
            "payload": history_payload,
            "created_at": now,
        }
        try:
            validate_interaction_history_entry(entry)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO request_interaction_history (
                    request_id, interaction_id, event_type, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    interaction_id,
                    event_type,
                    json.dumps(history_payload, sort_keys=True),
                    now,
                ),
            )
            await conn.commit()

    async def clear_pending_interaction(self, request_id: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = 'consumed', updated_at = ?
                WHERE request_id = ? AND state = 'pending'
                """,
                (now, request_id),
            )
            await conn.commit()

    async def list_interaction_history(self, request_id: str) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT interaction_id, event_type, payload_json, created_at
                FROM request_interaction_history
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            )
            rows = await cursor.fetchall()
        history: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Skipping interaction history row with invalid JSON: request_id=%s interaction_id=%s",
                    request_id,
                    row["interaction_id"],
                )
                continue
            normalized_payload = payload if isinstance(payload, dict) else {}
            if row["event_type"] == "reply" and isinstance(normalized_payload, dict):
                normalized_payload = dict(normalized_payload)
                normalized_payload.setdefault("source_attempt", 1)
            item = {
                "interaction_id": row["interaction_id"],
                "source_attempt": (
                    normalized_payload.get("source_attempt")
                    if isinstance(normalized_payload, dict)
                    and isinstance(normalized_payload.get("source_attempt"), int)
                    else 1
                ),
                "event_type": row["event_type"],
                "payload": normalized_payload,
                "created_at": row["created_at"],
            }
            try:
                validate_interaction_history_entry(item)
            except ProtocolSchemaViolation as exc:
                logger.warning(
                    "Skipping incompatible interaction history row: request_id=%s interaction_id=%s detail=%s",
                    request_id,
                    row["interaction_id"],
                    str(exc),
                )
                continue
            history.append(item)
        return history

    async def set_pending_interaction(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._database.ensure_initialized()
        normalized_payload = dict(payload)
        normalized_payload.setdefault("source_attempt", 1)
        try:
            validate_pending_interaction(normalized_payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        interaction_id = int(normalized_payload["interaction_id"])
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactions (
                    request_id, interaction_id, payload_json, state,
                    idempotency_key, reply_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    interaction_id,
                    json.dumps(normalized_payload, sort_keys=True),
                    "pending",
                    None,
                    None,
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def get_pending_interaction(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_interactions
                WHERE request_id = ? AND state = 'pending'
                ORDER BY interaction_id DESC
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
            logger.warning("Invalid pending interaction JSON ignored: request_id=%s", request_id)
            return None
        if isinstance(payload, dict) and "source_attempt" not in payload:
            payload["source_attempt"] = 1
        try:
            validate_pending_interaction(payload)
        except ProtocolSchemaViolation as exc:
            logger.warning(
                "Invalid pending interaction payload ignored: request_id=%s detail=%s",
                request_id,
                str(exc),
            )
            return None
        return payload

    async def get_interaction_count(self, request_id: str) -> int:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM request_interactions
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return 0
        return int(row["count"] or 0)

    async def get_auto_decision_stats(self, request_id: str) -> Dict[str, Any]:
        history = await self.list_interaction_history(request_id)
        auto_decision_count = 0
        last_auto_decision_at: Optional[str] = None
        for item in history:
            if item.get("event_type") != "reply":
                continue
            payload_obj = item.get("payload")
            if not isinstance(payload_obj, dict):
                continue
            if payload_obj.get("resolution_mode") != "auto_decide_timeout":
                continue
            auto_decision_count += 1
            resolved_at_obj = payload_obj.get("resolved_at")
            if isinstance(resolved_at_obj, str) and resolved_at_obj:
                if last_auto_decision_at is None or resolved_at_obj > last_auto_decision_at:
                    last_auto_decision_at = resolved_at_obj
        return {
            "auto_decision_count": auto_decision_count,
            "last_auto_decision_at": last_auto_decision_at,
        }

    async def get_interaction_reply(
        self, request_id: str, interaction_id: int, idempotency_key: str
    ) -> Optional[Any]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ? AND idempotency_key = ?
                """,
                (request_id, interaction_id, idempotency_key),
            )
            row = await cursor.fetchone()
        if not row or row["reply_json"] is None:
            return None
        return json.loads(row["reply_json"])

    async def consume_interaction_reply(self, request_id: str, interaction_id: int) -> Optional[Any]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT state, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            )
            row = await cursor.fetchone()
            if not row or row["state"] != "answered" or row["reply_json"] is None:
                return None
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = ?, updated_at = ?
                WHERE request_id = ? AND interaction_id = ?
                """,
                ("consumed", datetime.utcnow().isoformat(), request_id, interaction_id),
            )
            await conn.commit()
            return json.loads(row["reply_json"])

    async def submit_interaction_reply(
        self,
        request_id: str,
        interaction_id: int,
        response: Any,
        idempotency_key: Optional[str],
    ) -> str:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT state, idempotency_key, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            )
            row = await cursor.fetchone()
            if not row:
                return "stale"

            state = row["state"]
            existing_key = row["idempotency_key"]
            existing_reply = json.loads(row["reply_json"]) if row["reply_json"] is not None else None
            if state != "pending":
                if idempotency_key and existing_key == idempotency_key:
                    if existing_reply == response:
                        return "idempotent"
                    return "idempotency_conflict"
                return "stale"

            now = datetime.utcnow().isoformat()
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = ?, idempotency_key = ?, reply_json = ?, updated_at = ?
                WHERE request_id = ? AND interaction_id = ?
                """,
                (
                    "answered",
                    idempotency_key,
                    json.dumps(response, sort_keys=True),
                    now,
                    request_id,
                    interaction_id,
                ),
            )
            await conn.commit()
            return "accepted"
