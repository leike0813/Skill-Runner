import asyncio
import json
from datetime import datetime
from pathlib import Path

from server.config import config
from server.services.platform import aiosqlite_compat as aiosqlite


class RunStoreSchemaMigration:
    async def migrate_interactive_runtime_table(self, conn: aiosqlite.Connection) -> None:
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


class RunStoreDatabase:
    def __init__(self, db_path: Path, *, schema_migration: RunStoreSchemaMigration | None = None) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._schema_migration = schema_migration or RunStoreSchemaMigration()

    def connect(self):
        return aiosqlite.connect(str(self.db_path))

    async def ensure_initialized(self) -> None:
        if self._initialized and not self.db_path.exists():
            self._initialized = False
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized and not self.db_path.exists():
                self._initialized = False
            if self._initialized:
                return
            await self.init_db()
            self._initialized = True

    async def init_db(self) -> None:
        async with self.connect() as conn:
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
                CREATE TABLE IF NOT EXISTS engine_status_cache (
                    engine TEXT PRIMARY KEY,
                    present INTEGER NOT NULL,
                    version TEXT,
                    updated_at TEXT NOT NULL
                )
                """
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
            await self._schema_migration.migrate_interactive_runtime_table(conn)
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
