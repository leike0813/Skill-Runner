import asyncio
import contextlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from server.config import config
from server.services.platform import aiosqlite_compat as aiosqlite
from server.services.platform.sqlite_db_handle import sqlite_db_handle_registry

from .auth_session_durable_store import DURABLE_AUTH_SESSION_TABLE

logger = logging.getLogger(__name__)


SCHEMA_ALL = "all"
SCHEMA_CORE = "core"
SCHEMA_STATE = "state"
SCHEMA_INTERACTIONS = "interactions"
SCHEMA_AUTH = "auth"
SCHEMA_CACHE = "cache"


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
        if not runtime_cols or runtime_cols == expected_cols:
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
    def __init__(
        self,
        db_path: Path,
        *,
        schema_migration: RunStoreSchemaMigration | None = None,
        max_concurrent_connections: int = 16,
        schema: str = SCHEMA_ALL,
        legacy_source_db_path: Path | None = None,
    ) -> None:
        _ = max_concurrent_connections
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema = schema
        self.legacy_source_db_path = legacy_source_db_path
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._schema_migration = schema_migration or RunStoreSchemaMigration()

    def connect(self):
        return sqlite_db_handle_registry.operation(self.db_path)

    async def ensure_initialized(self) -> None:
        if self._initialized and not self.db_path.exists():
            await sqlite_db_handle_registry.close_path(self.db_path)
            self._initialized = False
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized and not self.db_path.exists():
                await sqlite_db_handle_registry.close_path(self.db_path)
                self._initialized = False
            if self._initialized:
                return
            await self.init_db()
            self._initialized = True

    async def init_db(self) -> None:
        async with self.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await self._apply_pragmas(conn)
            tables = await self._create_schema(conn)
            await self._copy_from_legacy_if_empty(conn, tables)
            if self.schema in {SCHEMA_ALL, SCHEMA_INTERACTIONS}:
                await self._schema_migration.migrate_interactive_runtime_table(conn)
            await conn.commit()

    async def _apply_pragmas(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout = 5000")

    async def _create_schema(self, conn: aiosqlite.Connection) -> list[str]:
        schemas = {self.schema}
        if self.schema == SCHEMA_ALL:
            schemas = {SCHEMA_CORE, SCHEMA_STATE, SCHEMA_INTERACTIONS, SCHEMA_AUTH, SCHEMA_CACHE, "legacy_misc"}
        tables: list[str] = []
        if SCHEMA_CORE in schemas:
            tables.extend(await self._create_core_schema(conn))
        if SCHEMA_STATE in schemas:
            tables.extend(await self._create_state_schema(conn))
        if SCHEMA_INTERACTIONS in schemas:
            tables.extend(await self._create_interaction_schema(conn))
        if SCHEMA_AUTH in schemas:
            tables.extend(await self._create_auth_schema(conn))
        if SCHEMA_CACHE in schemas:
            tables.extend(await self._create_cache_schema(conn))
        if "legacy_misc" in schemas:
            tables.extend(await self._create_legacy_misc_schema(conn))
        return tables

    async def _create_core_schema(self, conn: aiosqlite.Connection) -> list[str]:
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
                skill_package_hash TEXT,
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
        await self._ensure_columns(
            conn,
            "requests",
            {
                "run_id": "TEXT",
                "skill_source": "TEXT NOT NULL DEFAULT 'installed'",
                "input_json": "TEXT NOT NULL DEFAULT '{}'",
                "request_upload_mode": "TEXT NOT NULL DEFAULT 'none'",
                "temp_skill_package_sha256": "TEXT",
                "temp_skill_manifest_id": "TEXT",
                "temp_skill_manifest_json": "TEXT",
                "effective_runtime_options_json": "TEXT NOT NULL DEFAULT '{}'",
                "client_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
                "skill_package_hash": "TEXT",
            },
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
                workspace_id TEXT,
                workspace_dir TEXT,
                workspace_namespace TEXT,
                workspace_source_request_id TEXT,
                input_manifest_path TEXT,
                workspace_input_token TEXT,
                workspace_output_token TEXT,
                recovery_state TEXT NOT NULL DEFAULT 'none',
                recovered_at TEXT,
                recovery_reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._ensure_columns(
            conn,
            "runs",
            {
                "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
                "recovery_state": "TEXT NOT NULL DEFAULT 'none'",
                "recovered_at": "TEXT",
                "recovery_reason": "TEXT",
                "workspace_id": "TEXT",
                "workspace_dir": "TEXT",
                "workspace_namespace": "TEXT",
                "workspace_source_request_id": "TEXT",
                "input_manifest_path": "TEXT",
                "workspace_input_token": "TEXT",
                "workspace_output_token": "TEXT",
            },
        )
        await self._create_indexes(
            conn,
            [
                "CREATE INDEX IF NOT EXISTS idx_requests_run_id ON requests(run_id)",
                "CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_requests_status_created_at ON requests(status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_runs_status_created_at ON runs(status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_runs_workspace_id ON runs(workspace_id)",
                "CREATE INDEX IF NOT EXISTS idx_runs_workspace_dir ON runs(workspace_dir)",
            ],
        )
        return ["requests", "runs"]

    async def _create_state_schema(self, conn: aiosqlite.Connection) -> list[str]:
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
        await self._create_indexes(
            conn,
            [
                "CREATE INDEX IF NOT EXISTS idx_request_current_projection_status_updated_at ON request_current_projection(status, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_request_current_projection_run_id ON request_current_projection(run_id)",
                "CREATE INDEX IF NOT EXISTS idx_request_run_state_status_updated_at ON request_run_state(status, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_request_dispatch_state_run_id ON request_dispatch_state(run_id)",
                "CREATE INDEX IF NOT EXISTS idx_request_dispatch_state_phase_updated_at ON request_dispatch_state(phase, updated_at)",
            ],
        )
        return ["request_current_projection", "request_run_state", "request_dispatch_state"]

    async def _create_interaction_schema(self, conn: aiosqlite.Connection) -> list[str]:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS request_interactions (
                request_id TEXT NOT NULL,
                interaction_id INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                state TEXT NOT NULL,
                idempotency_key TEXT,
                reply_json TEXT,
                reply_public_json TEXT,
                reply_fingerprint TEXT,
                reply_receipt_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (request_id, interaction_id)
            )
            """
        )
        await self._ensure_columns(
            conn,
            "request_interactions",
            {
                "reply_public_json": "TEXT",
                "reply_fingerprint": "TEXT",
                "reply_receipt_json": "TEXT",
            },
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
        await self._create_indexes(
            conn,
            [
                "CREATE INDEX IF NOT EXISTS idx_request_interactions_pending ON request_interactions(request_id, state)",
                "CREATE INDEX IF NOT EXISTS idx_request_interaction_history_request_id_id ON request_interaction_history(request_id, id)",
                "CREATE INDEX IF NOT EXISTS idx_request_resume_tickets_state_updated_at ON request_resume_tickets(state, updated_at)",
            ],
        )
        return [
            "request_interactions",
            "request_interactive_runtime",
            "request_interaction_history",
            "request_resume_tickets",
        ]

    async def _create_auth_schema(self, conn: aiosqlite.Connection) -> list[str]:
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
            f"""
            CREATE TABLE IF NOT EXISTS {DURABLE_AUTH_SESSION_TABLE} (
                auth_session_id TEXT PRIMARY KEY,
                engine TEXT NOT NULL,
                provider_id TEXT,
                scope_key TEXT NOT NULL,
                request_id TEXT,
                run_id TEXT,
                source_attempt INTEGER,
                status TEXT NOT NULL,
                auth_method TEXT,
                challenge_kind TEXT,
                driver TEXT,
                execution_mode TEXT,
                transport TEXT,
                input_kind TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                last_error TEXT,
                resume_ticket_id TEXT,
                terminal_reason TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        await self._create_indexes(
            conn,
            [
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_request_auth_sessions_session_id ON request_auth_sessions(auth_session_id)",
                f"CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_scope_status ON {DURABLE_AUTH_SESSION_TABLE}(scope_key, status)",
                f"CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_request_status ON {DURABLE_AUTH_SESSION_TABLE}(request_id, status)",
                f"CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_run_status ON {DURABLE_AUTH_SESSION_TABLE}(run_id, status)",
            ],
        )
        return ["request_auth_sessions", "request_auth_method_selection", DURABLE_AUTH_SESSION_TABLE]

    async def _create_cache_schema(self, conn: aiosqlite.Connection) -> list[str]:
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
            CREATE TABLE IF NOT EXISTS skill_package_identities (
                skill_id TEXT PRIMARY KEY,
                skill_package_hash TEXT NOT NULL,
                source TEXT NOT NULL,
                skill_path TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS temp_skill_package_cache (
                skill_package_hash TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                snapshot_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        await self._create_indexes(
            conn,
            [
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_run_status ON cache_entries(run_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_temp_cache_entries_run_status ON temp_cache_entries(run_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_temp_skill_package_cache_expires_at ON temp_skill_package_cache(expires_at)",
            ],
        )
        return ["cache_entries", "temp_cache_entries", "skill_package_identities", "temp_skill_package_cache"]

    async def _create_legacy_misc_schema(self, conn: aiosqlite.Connection) -> list[str]:
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
        await self._create_indexes(
            conn,
            [
                "CREATE INDEX IF NOT EXISTS idx_process_leases_status ON process_leases(status)",
                "CREATE INDEX IF NOT EXISTS idx_process_leases_updated_at ON process_leases(updated_at)",
            ],
        )
        return ["process_leases", "engine_status_cache", "skill_installs"]

    async def _ensure_columns(self, conn: aiosqlite.Connection, table: str, columns: dict[str, str]) -> None:
        info_cur = await conn.execute(f"PRAGMA table_info({table})")
        existing_cols = {row["name"] for row in await info_cur.fetchall()}
        for name, definition in columns.items():
            if name not in existing_cols:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    async def _create_indexes(self, conn: aiosqlite.Connection, statements: Iterable[str]) -> None:
        for statement in statements:
            await conn.execute(statement)

    async def _copy_from_legacy_if_empty(self, conn: aiosqlite.Connection, tables: list[str]) -> None:
        legacy_path = self.legacy_source_db_path
        if not legacy_path or self.schema == SCHEMA_ALL:
            return
        if not legacy_path.exists():
            return
        try:
            if legacy_path.resolve() == self.db_path.resolve():
                return
        except OSError:
            return
        try:
            await conn.execute("ATTACH DATABASE ? AS legacy", (str(legacy_path),))
        except (OSError, RuntimeError, ValueError, TypeError, sqlite3.Error):
            logger.warning(
                "Best-effort legacy database attach failed: db=%s legacy=%s",
                self.db_path,
                legacy_path,
                exc_info=True,
            )
            return
        try:
            for table in tables:
                await self._copy_legacy_table_if_empty(conn, table)
        finally:
            with contextlib.suppress(OSError, RuntimeError, ValueError, TypeError, sqlite3.Error):
                await conn.execute("DETACH DATABASE legacy")

    async def _copy_legacy_table_if_empty(self, conn: aiosqlite.Connection, table: str) -> None:
        try:
            target_count_cur = await conn.execute(f"SELECT COUNT(1) AS count FROM {table}")
            target_count = int((await target_count_cur.fetchone())["count"] or 0)
            if target_count > 0:
                return
            legacy_exists_cur = await conn.execute(
                "SELECT name FROM legacy.sqlite_master WHERE type='table' AND name = ?",
                (table,),
            )
            if await legacy_exists_cur.fetchone() is None:
                return
            target_cols_cur = await conn.execute(f"PRAGMA table_info({table})")
            legacy_cols_cur = await conn.execute(f"PRAGMA legacy.table_info({table})")
            target_cols = [row["name"] for row in await target_cols_cur.fetchall()]
            legacy_cols = {row["name"] for row in await legacy_cols_cur.fetchall()}
            copy_cols = [col for col in target_cols if col in legacy_cols]
            if not copy_cols:
                return
            cols_sql = ", ".join(copy_cols)
            await conn.execute(
                f"INSERT OR IGNORE INTO {table} ({cols_sql}) SELECT {cols_sql} FROM legacy.{table}"
            )
        except (OSError, RuntimeError, ValueError, TypeError, sqlite3.Error):
            logger.warning(
                "Best-effort legacy table copy failed: db=%s table=%s",
                self.db_path,
                table,
                exc_info=True,
            )
