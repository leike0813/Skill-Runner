from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DURABLE_AUTH_SESSION_TABLE = "durable_auth_sessions"
DURABLE_AUTH_SESSION_ACTIVE_STATUSES = ("created", "challenge_active")
DURABLE_AUTH_SESSION_TERMINAL_STATUSES = (
    "succeeded",
    "failed",
    "canceled",
    "expired",
    "superseded",
)


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_auth_session_scope_key(engine: str, provider_id: str | None) -> str:
    normalized_engine = engine.strip().lower()
    normalized_provider = (provider_id or "_none_").strip().lower() or "_none_"
    return f"{normalized_engine}::{normalized_provider}"


class DurableAuthSessionSyncStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_initialized(self) -> None:
        with self._connect() as conn:
            conn.execute(
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
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_scope_status
                ON {DURABLE_AUTH_SESSION_TABLE} (scope_key, status)
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_request_status
                ON {DURABLE_AUTH_SESSION_TABLE} (request_id, status)
                """
            )
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{DURABLE_AUTH_SESSION_TABLE}_run_status
                ON {DURABLE_AUTH_SESSION_TABLE} (run_id, status)
                """
            )
            conn.commit()

    def upsert_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        request_id: str | None,
        run_id: str | None,
        source_attempt: int | None,
        challenge_kind: str | None = None,
        resume_ticket_id: str | None = None,
        terminal_reason: str | None = None,
        status_override: str | None = None,
    ) -> None:
        session_id = str(snapshot.get("session_id") or "").strip()
        engine = str(snapshot.get("engine") or "").strip().lower()
        if not session_id or not engine:
            return
        self.ensure_initialized()
        provider_id_obj = snapshot.get("provider_id")
        provider_id = str(provider_id_obj).strip() if isinstance(provider_id_obj, str) and provider_id_obj.strip() else None
        now = utc_iso_now()
        status = str(status_override or snapshot.get("status") or "").strip() or "created"
        payload = dict(snapshot)
        payload["status"] = status
        if challenge_kind:
            payload["challenge_kind"] = challenge_kind
        if terminal_reason:
            payload["terminal_reason"] = terminal_reason
        with self._connect() as conn:
            conn.execute(
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
                    session_id,
                    engine,
                    provider_id,
                    build_auth_session_scope_key(engine, provider_id),
                    request_id,
                    run_id,
                    int(source_attempt) if source_attempt is not None else None,
                    status,
                    snapshot.get("auth_method"),
                    challenge_kind,
                    snapshot.get("orchestrator"),
                    snapshot.get("execution_mode"),
                    snapshot.get("transport"),
                    snapshot.get("input_kind"),
                    snapshot.get("created_at") or now,
                    snapshot.get("updated_at") or now,
                    snapshot.get("expires_at"),
                    snapshot.get("error"),
                    resume_ticket_id,
                    terminal_reason,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            conn.commit()

    def mark_terminal(
        self,
        auth_session_id: str,
        *,
        status: str,
        last_error: str | None = None,
        terminal_reason: str | None = None,
    ) -> None:
        self.ensure_initialized()
        now = utc_iso_now()
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT payload_json FROM {DURABLE_AUTH_SESSION_TABLE} WHERE auth_session_id = ? LIMIT 1",
                (auth_session_id,),
            )
            row = cur.fetchone()
            payload: dict[str, Any] = {}
            if row is not None:
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError):
                    payload = {}
            payload["status"] = status
            if last_error is not None:
                payload["error"] = last_error
            if terminal_reason is not None:
                payload["terminal_reason"] = terminal_reason
            conn.execute(
                f"""
                UPDATE {DURABLE_AUTH_SESSION_TABLE}
                SET status = ?, updated_at = ?, last_error = COALESCE(?, last_error),
                    terminal_reason = COALESCE(?, terminal_reason), payload_json = ?
                WHERE auth_session_id = ?
                """,
                (
                    status,
                    now,
                    last_error,
                    terminal_reason,
                    json.dumps(payload, sort_keys=True),
                    auth_session_id,
                ),
            )
            conn.commit()

    def get_active_for_scope(self, *, engine: str, provider_id: str | None) -> dict[str, Any] | None:
        self.ensure_initialized()
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                SELECT payload_json
                FROM {DURABLE_AUTH_SESSION_TABLE}
                WHERE scope_key = ? AND status IN ({",".join("?" for _ in DURABLE_AUTH_SESSION_ACTIVE_STATUSES)})
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (build_auth_session_scope_key(engine, provider_id), *DURABLE_AUTH_SESSION_ACTIVE_STATUSES),
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None

    def get_session(self, auth_session_id: str) -> dict[str, Any] | None:
        self.ensure_initialized()
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT payload_json FROM {DURABLE_AUTH_SESSION_TABLE} WHERE auth_session_id = ? LIMIT 1",
                (auth_session_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None
