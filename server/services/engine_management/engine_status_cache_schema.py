from __future__ import annotations

from server.services.platform import aiosqlite_compat as aiosqlite


CREATE_ENGINE_STATUS_CACHE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS engine_status_cache (
    engine TEXT PRIMARY KEY,
    present INTEGER NOT NULL,
    version TEXT,
    last_error TEXT,
    updated_at TEXT NOT NULL
)
"""


async def ensure_engine_status_cache_schema(conn: aiosqlite.Connection) -> None:
    """Create the cache table and apply additive migrations in place."""
    await conn.execute(CREATE_ENGINE_STATUS_CACHE_TABLE_SQL)
    cursor = await conn.execute("PRAGMA table_info(engine_status_cache)")
    columns = {str(row[1]) for row in await cursor.fetchall() if len(row) > 1}
    if "last_error" not in columns:
        await conn.execute("ALTER TABLE engine_status_cache ADD COLUMN last_error TEXT")
    await conn.commit()
