import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
from server.services.engine_management.engine_auth_flow_manager import engine_auth_flow_manager
from server.services.platform import aiosqlite_compat as aiosqlite


class RunStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.RUNS_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def _connect(self):
        return aiosqlite.connect(str(self.db_path))

    async def _ensure_initialized(self) -> None:
        if self._initialized and not self.db_path.exists():
            self._initialized = False
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized and not self.db_path.exists():
                self._initialized = False
            if self._initialized:
                return
            await self._init_db()
            self._initialized = True

    async def _init_db(self) -> None:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    skill_source TEXT NOT NULL DEFAULT 'installed',
                    engine TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    parameter_json TEXT NOT NULL,
                    engine_options_json TEXT NOT NULL,
                    runtime_options_json TEXT NOT NULL,
                    effective_runtime_options_json TEXT NOT NULL DEFAULT '{}',
                    client_metadata_json TEXT NOT NULL DEFAULT '{}',
                    input_manifest_path TEXT,
                    input_manifest_hash TEXT,
                    skill_fingerprint TEXT,
                    cache_key TEXT,
                    request_upload_mode TEXT NOT NULL DEFAULT 'none',
                    temp_skill_package_sha256 TEXT,
                    temp_skill_manifest_id TEXT,
                    temp_skill_manifest_json TEXT,
                    run_id TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            request_info_cur = await conn.execute("PRAGMA table_info(requests)")
            existing_cols = {row["name"] for row in await request_info_cur.fetchall()}
            if "run_id" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN run_id TEXT")
            if "skill_source" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN skill_source TEXT NOT NULL DEFAULT 'installed'")
            if "input_json" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN input_json TEXT NOT NULL DEFAULT '{}'")
            if "request_upload_mode" not in existing_cols:
                await conn.execute(
                    "ALTER TABLE requests ADD COLUMN request_upload_mode TEXT NOT NULL DEFAULT 'none'"
                )
            if "temp_skill_package_sha256" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN temp_skill_package_sha256 TEXT")
            if "temp_skill_manifest_id" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN temp_skill_manifest_id TEXT")
            if "temp_skill_manifest_json" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN temp_skill_manifest_json TEXT")
            if "effective_runtime_options_json" not in existing_cols:
                await conn.execute(
                    "ALTER TABLE requests ADD COLUMN effective_runtime_options_json TEXT NOT NULL DEFAULT '{}'"
                )
                await conn.execute(
                    """
                    UPDATE requests
                    SET effective_runtime_options_json = runtime_options_json
                    WHERE effective_runtime_options_json IS NULL
                       OR effective_runtime_options_json = ''
                       OR effective_runtime_options_json = '{}'
                    """
                )
            if "client_metadata_json" not in existing_cols:
                await conn.execute(
                    "ALTER TABLE requests ADD COLUMN client_metadata_json TEXT NOT NULL DEFAULT '{}'"
                )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    cache_key TEXT,
                    status TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result_path TEXT,
                    artifacts_manifest_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            run_info_cur = await conn.execute("PRAGMA table_info(runs)")
            run_cols = {row["name"] for row in await run_info_cur.fetchall()}
            if "cancel_requested" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
            if "recovery_state" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovery_state TEXT NOT NULL DEFAULT 'none'")
            if "recovered_at" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovered_at TEXT")
            if "recovery_reason" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovery_reason TEXT")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temp_cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_installs (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    skill_id TEXT,
                    version TEXT,
                    action TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS process_leases (
                    lease_id TEXT PRIMARY KEY,
                    owner_kind TEXT,
                    owner_id TEXT,
                    pid INTEGER,
                    request_id TEXT,
                    run_id TEXT,
                    attempt_number INTEGER,
                    engine TEXT,
                    transport TEXT,
                    metadata_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT,
                    close_reason TEXT
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_process_leases_status ON process_leases(status)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_process_leases_updated_at ON process_leases(updated_at)"
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interactions (
                    request_id TEXT NOT NULL,
                    interaction_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    idempotency_key TEXT,
                    reply_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (request_id, interaction_id)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interactive_runtime (
                    request_id TEXT PRIMARY KEY,
                    effective_session_timeout_sec INTEGER,
                    session_handle_json TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await self._migrate_interactive_runtime_table(conn)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interaction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    interaction_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_auth_sessions (
                    request_id TEXT PRIMARY KEY,
                    auth_session_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    submission_kind TEXT,
                    submission_redacted_json TEXT,
                    auth_resume_context_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_auth_method_selection (
                    request_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_resume_tickets (
                    request_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    cause TEXT NOT NULL,
                    source_attempt INTEGER NOT NULL,
                    target_attempt INTEGER NOT NULL,
                    payload_json TEXT,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    dispatched_at TEXT,
                    started_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_current_projection (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_attempt INTEGER NOT NULL,
                    pending_owner TEXT,
                    pending_interaction_id INTEGER,
                    pending_auth_session_id TEXT,
                    resume_ticket_id TEXT,
                    resume_cause TEXT,
                    source_attempt INTEGER,
                    target_attempt INTEGER,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_run_state (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_attempt INTEGER NOT NULL,
                    pending_owner TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_dispatch_state (
                    request_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    dispatch_ticket_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    worker_claim_id TEXT,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_interactions_pending
                ON request_interactions (request_id, state)
                """
            )
            await conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_request_auth_sessions_session_id
                ON request_auth_sessions (auth_session_id)
                """
            )
            await conn.commit()

    async def _migrate_interactive_runtime_table(self, conn: aiosqlite.Connection) -> None:
        runtime_cur = await conn.execute("PRAGMA table_info(request_interactive_runtime)")
        runtime_cols = {row["name"] for row in await runtime_cur.fetchall()}
        expected_cols = {
            "request_id",
            "effective_session_timeout_sec",
            "session_handle_json",
            "updated_at",
        }
        if runtime_cols == expected_cols:
            return

        now = datetime.utcnow().isoformat()
        await conn.execute("ALTER TABLE request_interactive_runtime RENAME TO request_interactive_runtime_legacy")
        await conn.execute(
            """
            CREATE TABLE request_interactive_runtime (
                request_id TEXT PRIMARY KEY,
                effective_session_timeout_sec INTEGER,
                session_handle_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        legacy_cur = await conn.execute("SELECT * FROM request_interactive_runtime_legacy")
        legacy_rows = await legacy_cur.fetchall()
        for row in legacy_rows:
            row_dict = dict(row)
            request_id = row_dict.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                continue
            timeout_obj = row_dict.get("effective_session_timeout_sec")
            timeout_value: int | None = None
            if timeout_obj is not None:
                try:
                    timeout_value = int(timeout_obj)
                except (TypeError, ValueError, OverflowError):
                    timeout_value = None
            if timeout_value is None:
                profile_raw = row_dict.get("profile_json")
                if isinstance(profile_raw, str) and profile_raw:
                    try:
                        profile = json.loads(profile_raw)
                    except (json.JSONDecodeError, TypeError):
                        profile = {}
                    timeout_from_profile = profile.get("session_timeout_sec")
                    if timeout_from_profile is not None:
                        try:
                            timeout_value = int(timeout_from_profile)
                        except (TypeError, ValueError, OverflowError):
                            timeout_value = None
            if timeout_value is None:
                timeout_value = int(config.SYSTEM.SESSION_TIMEOUT_SEC)
            handle_obj = row_dict.get("session_handle_json")
            handle_json = handle_obj if isinstance(handle_obj, str) else None
            updated_at_obj = row_dict.get("updated_at")
            updated_at = updated_at_obj if isinstance(updated_at_obj, str) and updated_at_obj else now
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactive_runtime (
                    request_id, effective_session_timeout_sec, session_handle_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (request_id, timeout_value, handle_json, updated_at),
            )
        await conn.execute("DROP TABLE request_interactive_runtime_legacy")

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
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO requests (
                    request_id, skill_id, skill_source, engine, input_json, parameter_json,
                    engine_options_json, runtime_options_json, effective_runtime_options_json,
                    client_metadata_json, request_upload_mode, temp_skill_package_sha256,
                    temp_skill_manifest_id, temp_skill_manifest_json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    skill_id,
                    skill_source,
                    engine,
                    json.dumps(input_data or {}, sort_keys=True),
                    json.dumps(parameter, sort_keys=True),
                    json.dumps(engine_options, sort_keys=True),
                    json.dumps(runtime_options, sort_keys=True),
                    json.dumps(effective_runtime_options or runtime_options, sort_keys=True),
                    json.dumps(client_metadata or {}, sort_keys=True),
                    request_upload_mode,
                    temp_skill_package_sha256,
                    temp_skill_manifest_id,
                    (
                        json.dumps(temp_skill_manifest_json, sort_keys=True)
                        if temp_skill_manifest_json is not None
                        else None
                    ),
                    "created",
                    created_at,
                ),
            )
            await conn.commit()

    async def update_request_manifest(
        self,
        request_id: str,
        manifest_path: str | None,
        manifest_hash: str,
        *,
        request_upload_mode: str | None = None,
    ) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET input_manifest_path = ?, input_manifest_hash = ?,
                    request_upload_mode = COALESCE(?, request_upload_mode)
                WHERE request_id = ?
                """,
                (manifest_path, manifest_hash, request_upload_mode, request_id),
            )
            await conn.commit()

    async def update_request_cache_key(self, request_id: str, cache_key: str, skill_fingerprint: str) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET cache_key = ?, skill_fingerprint = ?, status = ?
                WHERE request_id = ?
                """,
                (cache_key, skill_fingerprint, "ready", request_id),
            )
            await conn.commit()

    async def update_request_skill_identity(
        self,
        request_id: str,
        *,
        skill_id: str,
        temp_skill_manifest_id: str | None = None,
        temp_skill_manifest_json: Dict[str, Any] | None = None,
        temp_skill_package_sha256: str | None = None,
    ) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET skill_id = ?,
                    temp_skill_manifest_id = COALESCE(?, temp_skill_manifest_id),
                    temp_skill_manifest_json = COALESCE(?, temp_skill_manifest_json),
                    temp_skill_package_sha256 = COALESCE(?, temp_skill_package_sha256)
                WHERE request_id = ?
                """,
                (
                    skill_id,
                    temp_skill_manifest_id,
                    (
                        json.dumps(temp_skill_manifest_json, sort_keys=True)
                        if temp_skill_manifest_json is not None
                        else None
                    ),
                    temp_skill_package_sha256,
                    request_id,
                ),
            )
            await conn.commit()

    async def update_request_run_id(self, request_id: str, run_id: str) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET run_id = ?, status = ?
                WHERE request_id = ?
                """,
                (run_id, "running", request_id),
            )
            await conn.commit()

    async def bind_request_run_id(self, request_id: str, run_id: str, *, status: str = "queued") -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET run_id = ?, status = ?
                WHERE request_id = ?
                """,
                (run_id, status, request_id),
            )
            await conn.commit()

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        data["effective_runtime_options"] = json.loads(
            data.get("effective_runtime_options_json") or data["runtime_options_json"]
        )
        data["client_metadata"] = json.loads(data.get("client_metadata_json") or "{}")
        return data

    async def get_request_with_run(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.skill_source AS skill_source,
                    req.engine AS engine,
                    req.run_id AS run_id,
                    req.runtime_options_json AS runtime_options_json,
                    req.effective_runtime_options_json AS effective_runtime_options_json,
                    req.client_metadata_json AS client_metadata_json,
                    req.created_at AS request_created_at,
                    run.status AS run_status,
                    run.created_at AS run_created_at,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason
                FROM requests req
                LEFT JOIN runs run ON req.run_id = run.run_id
                WHERE req.request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        runtime_options_raw = data.pop("runtime_options_json", "{}")
        try:
            data["runtime_options"] = json.loads(runtime_options_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["runtime_options"] = {}
        effective_runtime_options_raw = data.pop("effective_runtime_options_json", "{}")
        try:
            data["effective_runtime_options"] = json.loads(
                effective_runtime_options_raw or "{}"
            )
        except (json.JSONDecodeError, TypeError):
            data["effective_runtime_options"] = dict(data["runtime_options"])
        client_metadata_raw = data.pop("client_metadata_json", "{}")
        try:
            data["client_metadata"] = json.loads(client_metadata_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["client_metadata"] = {}
        return data

    async def get_request_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        data["effective_runtime_options"] = json.loads(
            data.get("effective_runtime_options_json") or data["runtime_options_json"]
        )
        data["client_metadata"] = json.loads(data.get("client_metadata_json") or "{}")
        return data

    async def list_requests_with_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        safe_limit = max(1, min(int(limit), 1000))
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.skill_source AS skill_source,
                    req.engine AS engine,
                    req.run_id AS run_id,
                    req.created_at AS request_created_at,
                    run.status AS run_status,
                    run.created_at AS run_created_at,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason
                FROM requests req
                LEFT JOIN runs run ON req.run_id = run.run_id
                WHERE req.run_id IS NOT NULL
                ORDER BY req.created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def create_run(
        self,
        run_id: str,
        cache_key: Optional[str],
        status: str,
        result_path: str = "",
        artifacts_manifest_path: str = "",
    ) -> None:
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO runs (
                    run_id, cache_key, status, cancel_requested, result_path, artifacts_manifest_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, cache_key, status, 0, result_path, artifacts_manifest_path, created_at),
            )
            await conn.commit()

    async def update_run_status(self, run_id: str, status: str, result_path: Optional[str] = None) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            if result_path is not None:
                await conn.execute(
                    "UPDATE runs SET status = ?, result_path = ? WHERE run_id = ?",
                    (status, result_path, run_id),
                )
            else:
                await conn.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (status, run_id),
                )
            await conn.commit()

    async def set_current_projection(self, request_id: str, projection: Dict[str, Any]) -> None:
        await self._ensure_initialized()
        model = CurrentRunProjection.model_validate(projection)
        payload = model.model_dump(mode="json")
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        model = RunStateEnvelope.model_validate(state)
        payload = model.model_dump(mode="json")
        pending_owner_obj = payload.get("pending", {}).get("owner")
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                "DELETE FROM request_run_state WHERE request_id = ?",
                (request_id,),
            )
            await conn.commit()

    async def set_dispatch_state(self, request_id: str, state: Dict[str, Any]) -> None:
        await self._ensure_initialized()
        model = RunDispatchEnvelope.model_validate(state)
        payload = model.model_dump(mode="json")
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                "DELETE FROM request_dispatch_state WHERE request_id = ?",
                (request_id,),
            )
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
            try:
                projection = CurrentRunProjection(
                    request_id=str(state_payload.get("request_id") or ""),
                    run_id=str(state_payload.get("run_id") or ""),
                    status=state_payload.get("status", RunStatus.QUEUED.value),
                    updated_at=state_payload.get("updated_at"),
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
                logger.warning("Failed to convert run state into current projection: request_id=%s", request_id, exc_info=True)
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                "DELETE FROM request_current_projection WHERE request_id = ?",
                (request_id,),
            )
            await conn.commit()

    async def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="cache_entries", cache_key=cache_key, run_id=run_id)

    async def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="temp_cache_entries", cache_key=cache_key, run_id=run_id)

    async def _record_cache_entry(self, table: str, cache_key: str, run_id: str) -> None:
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (cache_key, run_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, run_id, "succeeded", created_at),
            )
            await conn.commit()

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="cache_entries", cache_key=cache_key)

    async def get_temp_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="temp_cache_entries", cache_key=cache_key)

    async def get_cached_run_for_source(self, cache_key: str, source: str) -> Optional[str]:
        if source == "temp_upload":
            return await self.get_temp_cached_run(cache_key)
        return await self.get_cached_run(cache_key)

    async def _get_cached_run(self, table: str, cache_key: str) -> Optional[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT run_id FROM {table} WHERE cache_key = ? AND status = ?",
                (cache_key, "succeeded"),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return row["run_id"]

    async def list_runs_for_cleanup(self, retention_days: int) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        if retention_days <= 0:
            return []
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        candidates = []
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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

    async def list_request_ids(self) -> List[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT request_id FROM requests")
            rows = await cursor.fetchall()
        return [row["request_id"] for row in rows]

    async def clear_all(self) -> Dict[str, int]:
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?, ?, ?)",
                ("queued", "running", "waiting_user", "waiting_auth"),
            )
            rows = await cursor.fetchall()
        return [row["run_id"] for row in rows if row["run_id"]]

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

    async def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        recovered_ts = recovered_at or datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        next_value = 1 if requested else 0
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT cancel_requested FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return False
        return int(row["cancel_requested"] or 0) == 1

    async def _upsert_interactive_runtime(
        self,
        request_id: str,
        *,
        effective_session_timeout_sec: Optional[int] = None,
        session_handle_json: Optional[str] = None,
    ) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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

    async def append_interaction_history(
        self,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: Dict[str, Any],
        *,
        source_attempt: int,
    ) -> None:
        await self._ensure_initialized()
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
        async with self._connect() as conn:
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

    async def issue_resume_ticket(
        self,
        request_id: str,
        *,
        cause: str,
        source_attempt: int,
        target_attempt: int,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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

    async def clear_pending_interaction(self, request_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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

    async def set_pending_auth(
        self,
        request_id: str,
        payload: Dict[str, Any],
        *,
        auth_resume_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_initialized()
        try:
            validate_pending_auth(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        try:
            validate_pending_auth_method_selection(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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

    async def get_pending_auth(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
            if isinstance(auth_session_id, str) and auth_session_id:
                try:
                    snapshot = engine_auth_flow_manager.get_session(auth_session_id)
                except KeyError:
                    snapshot = None
            created_at = (
                snapshot.get("created_at")
                if isinstance(snapshot, dict) and isinstance(snapshot.get("created_at"), str)
                else pending_auth.get("created_at")
            )
            expires_at = (
                snapshot.get("expires_at")
                if isinstance(snapshot, dict) and isinstance(snapshot.get("expires_at"), str)
                else pending_auth.get("expires_at")
            )
            timed_out = False
            status_obj = snapshot.get("status") if isinstance(snapshot, dict) else None
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
                    else pending_auth.get("last_error")
                ),
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

    async def list_interaction_history(self, request_id: str) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
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
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        await self._ensure_initialized()
        async with self._connect() as conn:
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
        """
        Returns one of: accepted | idempotent | stale | idempotency_conflict.
        """
        await self._ensure_initialized()
        async with self._connect() as conn:
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


run_store = RunStore()
logger = logging.getLogger(__name__)
