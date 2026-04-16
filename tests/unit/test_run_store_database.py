import sqlite3

import pytest

from server.services.orchestration.run_store_database import RunStoreDatabase


@pytest.mark.asyncio
async def test_run_store_database_initializes_requests_table(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    await database.ensure_initialized()

    with sqlite3.connect(database.db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='requests'"
        ).fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_run_store_database_reinitializes_after_db_file_deleted(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    await database.ensure_initialized()
    assert database.db_path.exists()
    database.db_path.unlink()

    await database.ensure_initialized()

    with sqlite3.connect(database.db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='requests'"
        ).fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_run_store_schema_migration_legacy_interactive_runtime(tmp_path):
    db_path = tmp_path / "runs.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE request_interactive_runtime (
                request_id TEXT PRIMARY KEY,
                profile_json TEXT,
                effective_session_timeout_sec INTEGER,
                session_handle_json TEXT,
                wait_deadline_at TEXT,
                process_binding_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO request_interactive_runtime (
                request_id, profile_json, effective_session_timeout_sec,
                session_handle_json, wait_deadline_at, process_binding_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-legacy",
                '{"kind":"sticky_process","session_timeout_sec":900}',
                None,
                '{"engine":"codex","handle_type":"session_id","handle_value":"thread-1","created_at_turn":1}',
                "2099-01-01T00:00:00",
                '{"run_id":"run-1","alive":true}',
                "2026-02-23T00:00:00",
            ),
        )
        conn.commit()

    database = RunStoreDatabase(db_path)
    await database.ensure_initialized()

    with sqlite3.connect(database.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(request_interactive_runtime)").fetchall()
        }
        row = conn.execute(
            "SELECT request_id, effective_session_timeout_sec, session_handle_json FROM request_interactive_runtime WHERE request_id = ?",
            ("req-legacy",),
        ).fetchone()

    assert cols == {
        "request_id",
        "effective_session_timeout_sec",
        "session_handle_json",
        "updated_at",
    }
    assert row["request_id"] == "req-legacy"
    assert row["effective_session_timeout_sec"] == 900
    assert '"handle_value":"thread-1"' in row["session_handle_json"]
