import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from server.services.platform import aiosqlite_compat as aiosqlite

from .run_store_database import RunStoreDatabase


class RunRequestStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

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
        skill_package_hash: Optional[str] = None,
    ) -> None:
        await self._database.ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO requests (
                    request_id, skill_id, skill_source, engine, input_json, parameter_json,
                    engine_options_json, runtime_options_json, effective_runtime_options_json,
                    client_metadata_json, request_upload_mode, temp_skill_package_sha256,
                    skill_package_hash, temp_skill_manifest_id, temp_skill_manifest_json,
                    status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    skill_package_hash,
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
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
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

    async def update_request_effective_runtime_options(
        self,
        request_id: str,
        effective_runtime_options: Dict[str, Any],
    ) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET effective_runtime_options_json = ?
                WHERE request_id = ?
                """,
                (json.dumps(effective_runtime_options, sort_keys=True), request_id),
            )
            await conn.commit()

    async def update_request_engine_options(
        self,
        request_id: str,
        engine_options: Dict[str, Any],
    ) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET engine_options_json = ?
                WHERE request_id = ?
                """,
                (json.dumps(engine_options, sort_keys=True), request_id),
            )
            await conn.commit()

    async def update_request_cache_key(
        self,
        request_id: str,
        cache_key: str,
        skill_fingerprint: str,
        *,
        skill_package_hash: str | None = None,
    ) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET cache_key = ?,
                    skill_fingerprint = ?,
                    skill_package_hash = COALESCE(?, skill_package_hash),
                    status = ?
                WHERE request_id = ?
                """,
                (cache_key, skill_fingerprint, skill_package_hash, "ready", request_id),
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
        skill_package_hash: str | None = None,
    ) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET skill_id = ?,
                    temp_skill_manifest_id = COALESCE(?, temp_skill_manifest_id),
                    temp_skill_manifest_json = COALESCE(?, temp_skill_manifest_json),
                    temp_skill_package_sha256 = COALESCE(?, temp_skill_package_sha256),
                    skill_package_hash = COALESCE(?, skill_package_hash)
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
                    skill_package_hash,
                    request_id,
                ),
            )
            await conn.commit()

    async def update_request_run_id(self, request_id: str, run_id: str) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
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
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
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
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,))
            row = await cursor.fetchone()
            run_row = None
            if row and row["run_id"]:
                run_cursor = await conn.execute("SELECT * FROM runs WHERE run_id = ?", (row["run_id"],))
                run_row = await run_cursor.fetchone()
        if not row:
            return None
        data = self._decode_request_row(row)
        if run_row:
            data.update(
                {
                    "run_status": run_row["status"],
                    "result_path": run_row["result_path"],
                    "artifacts_manifest_path": run_row["artifacts_manifest_path"],
                    "workspace_id": run_row["workspace_id"],
                    "workspace_dir": run_row["workspace_dir"],
                    "workspace_namespace": run_row["workspace_namespace"],
                    "workspace_source_request_id": run_row["workspace_source_request_id"],
                    "run_input_manifest_path": run_row["input_manifest_path"],
                    "workspace_input_token": run_row["workspace_input_token"],
                    "workspace_output_token": run_row["workspace_output_token"],
                }
            )
        return data

    async def get_request_with_run(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.skill_source AS skill_source,
                    req.engine AS engine,
                    req.engine_options_json AS engine_options_json,
                    req.run_id AS run_id,
                    req.runtime_options_json AS runtime_options_json,
                    req.effective_runtime_options_json AS effective_runtime_options_json,
                    req.client_metadata_json AS client_metadata_json,
                    req.created_at AS request_created_at,
                    run.status AS run_status,
                    run.created_at AS run_created_at,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason,
                    run.result_path AS result_path,
                    run.artifacts_manifest_path AS artifacts_manifest_path,
                    run.workspace_id AS workspace_id,
                    run.workspace_dir AS workspace_dir,
                    run.workspace_namespace AS workspace_namespace,
                    run.workspace_source_request_id AS workspace_source_request_id,
                    run.input_manifest_path AS run_input_manifest_path,
                    run.workspace_input_token AS workspace_input_token,
                    run.workspace_output_token AS workspace_output_token
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
            data["engine_options"] = json.loads(data.pop("engine_options_json", "{}") or "{}")
        except (json.JSONDecodeError, TypeError):
            data["engine_options"] = {}
        try:
            data["runtime_options"] = json.loads(runtime_options_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["runtime_options"] = {}
        effective_runtime_options_raw = data.pop("effective_runtime_options_json", "{}")
        try:
            data["effective_runtime_options"] = json.loads(effective_runtime_options_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["effective_runtime_options"] = dict(data["runtime_options"])
        client_metadata_raw = data.pop("client_metadata_json", "{}")
        try:
            data["client_metadata"] = json.loads(client_metadata_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["client_metadata"] = {}
        return data

    async def get_request_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
            run_row = None
            if row:
                run_cursor = await conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                run_row = await run_cursor.fetchone()
        if not row:
            return None
        data = self._decode_request_row(row)
        if run_row:
            data.update(
                {
                    "run_status": run_row["status"],
                    "result_path": run_row["result_path"],
                    "artifacts_manifest_path": run_row["artifacts_manifest_path"],
                    "workspace_id": run_row["workspace_id"],
                    "workspace_dir": run_row["workspace_dir"],
                    "workspace_namespace": run_row["workspace_namespace"],
                    "workspace_source_request_id": run_row["workspace_source_request_id"],
                    "run_input_manifest_path": run_row["input_manifest_path"],
                    "workspace_input_token": run_row["workspace_input_token"],
                    "workspace_output_token": run_row["workspace_output_token"],
                }
            )
        return data

    async def list_requests_with_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        safe_limit = max(1, min(int(limit), 1000))
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.skill_source AS skill_source,
                    req.engine AS engine,
                    req.engine_options_json AS engine_options_json,
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

    async def count_requests_with_runs(self) -> int:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT COUNT(1) AS total
                FROM requests req
                WHERE req.run_id IS NOT NULL
                """
            )
            row = await cursor.fetchone()
        if not row:
            return 0
        total_obj = row["total"]
        try:
            total = int(total_obj)
        except (TypeError, ValueError):
            return 0
        return max(0, total)

    async def list_requests_with_runs_page(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        safe_page_size = max(1, min(int(page_size), 1000))
        safe_page = max(1, int(page))
        offset = (safe_page - 1) * safe_page_size
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.skill_source AS skill_source,
                    req.engine AS engine,
                    req.engine_options_json AS engine_options_json,
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
                LIMIT ? OFFSET ?
                """,
                (safe_page_size, offset),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_request_ids(self) -> List[str]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT request_id FROM requests")
            rows = await cursor.fetchall()
        return [row["request_id"] for row in rows]

    def _decode_request_row(self, row: aiosqlite.Row) -> Dict[str, Any]:
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


class RunRegistryStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def create_run(
        self,
        run_id: str,
        cache_key: Optional[str],
        status: str,
        result_path: str = "",
        artifacts_manifest_path: str = "",
        workspace_id: str | None = None,
        workspace_dir: str | None = None,
        workspace_namespace: str | None = None,
        workspace_source_request_id: str | None = None,
        input_manifest_path: str | None = None,
        workspace_input_token: str | None = None,
        workspace_output_token: str | None = None,
    ) -> None:
        await self._database.ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO runs (
                    run_id, cache_key, status, cancel_requested, result_path, artifacts_manifest_path,
                    workspace_id, workspace_dir, workspace_namespace, workspace_source_request_id,
                    input_manifest_path, workspace_input_token, workspace_output_token, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    cache_key,
                    status,
                    0,
                    result_path,
                    artifacts_manifest_path,
                    workspace_id,
                    workspace_dir,
                    workspace_namespace,
                    workspace_source_request_id,
                    input_manifest_path,
                    workspace_input_token,
                    workspace_output_token,
                    created_at,
                ),
            )
            await conn.commit()

    async def update_run_status(self, run_id: str, status: str, result_path: Optional[str] = None) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
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

    async def update_run_workspace_metadata(
        self,
        run_id: str,
        *,
        result_path: str | None = None,
        input_manifest_path: str | None = None,
        workspace_output_token: str | None = None,
    ) -> None:
        await self._database.ensure_initialized()
        assignments: list[str] = []
        values: list[Any] = []
        if result_path is not None:
            assignments.append("result_path = ?")
            values.append(result_path)
        if input_manifest_path is not None:
            assignments.append("input_manifest_path = ?")
            values.append(input_manifest_path)
        if workspace_output_token is not None:
            assignments.append("workspace_output_token = ?")
            values.append(workspace_output_token)
        if not assignments:
            return
        values.append(run_id)
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"UPDATE runs SET {', '.join(assignments)} WHERE run_id = ?",
                tuple(values),
            )
            await conn.commit()

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
