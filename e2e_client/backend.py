from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx

RunSource = Literal["installed", "temp"]
RUN_SOURCE_INSTALLED: RunSource = "installed"
RUN_SOURCE_TEMP: RunSource = "temp"


class BackendApiError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Backend API error: {status_code} {detail}")


class BackendClient:
    async def list_management_engines(self) -> dict[str, Any]:
        raise NotImplementedError

    async def list_skills(self) -> dict[str, Any]:
        raise NotImplementedError

    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_skill_schemas(self, skill_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_engine_detail(self, engine: str) -> dict[str, Any]:
        raise NotImplementedError

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def create_temp_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def upload_run_file(self, request_id: str, zip_bytes: bytes) -> dict[str, Any]:
        raise NotImplementedError

    async def upload_temp_run(
        self,
        request_id: str,
        *,
        skill_package_zip: bytes,
        input_zip: bytes | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_state(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_pending(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def post_run_reply(
        self,
        request_id: str,
        payload: dict[str, Any],
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_result(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_artifacts(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_bundle(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> bytes:
        raise NotImplementedError

    def stream_run_events(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        cursor: int = 0,
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError

    async def get_run_event_history(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        from_seq: int | None = None,
        to_seq: int | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_run_log_range(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        stream: str,
        byte_from: int = 0,
        byte_to: int = 0,
    ) -> dict[str, Any]:
        raise NotImplementedError


class HttpBackendClient(BackendClient):
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def list_management_engines(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/management/engines")

    async def list_skills(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/management/skills")

    async def get_skill_detail(self, skill_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/v1/management/skills/{skill_id}")

    async def get_skill_schemas(self, skill_id: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/v1/management/skills/{skill_id}/schemas",
        )

    async def get_engine_detail(self, engine: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/v1/management/engines/{engine}",
        )

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", "/v1/jobs", json_payload=payload)

    async def create_temp_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", "/v1/temp-skill-runs", json_payload=payload)

    async def upload_run_file(self, request_id: str, zip_bytes: bytes) -> dict[str, Any]:
        files = {
            "file": ("input.zip", zip_bytes, "application/zip"),
        }
        return await self._request_json(
            "POST",
            f"/v1/jobs/{request_id}/upload",
            files=files,
        )

    async def upload_temp_run(
        self,
        request_id: str,
        *,
        skill_package_zip: bytes,
        input_zip: bytes | None = None,
    ) -> dict[str, Any]:
        files: dict[str, tuple[str, bytes, str]] = {
            "skill_package": ("skill_package.zip", skill_package_zip, "application/zip"),
        }
        if input_zip is not None:
            files["file"] = ("input.zip", input_zip, "application/zip")
        return await self._request_json(
            "POST",
            f"/v1/temp-skill-runs/{request_id}/upload",
            files=files,
        )

    async def get_run_state(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        return await self._request_json("GET", self._run_base_path(request_id, run_source=run_source))

    async def get_run_pending(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"{self._run_base_path(request_id, run_source=run_source)}/interaction/pending",
        )

    async def post_run_reply(
        self,
        request_id: str,
        payload: dict[str, Any],
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"{self._run_base_path(request_id, run_source=run_source)}/interaction/reply",
            json_payload=payload,
        )

    async def get_run_result(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if run_source == RUN_SOURCE_TEMP:
            return await self._request_json("GET", f"/v1/temp-skill-runs/{request_id}/result")
        return await self._request_json("GET", f"/v1/jobs/{request_id}/result")

    async def get_run_artifacts(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> dict[str, Any]:
        if run_source == RUN_SOURCE_TEMP:
            return await self._request_json("GET", f"/v1/temp-skill-runs/{request_id}/artifacts")
        return await self._request_json("GET", f"/v1/jobs/{request_id}/artifacts")

    async def get_run_bundle(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
    ) -> bytes:
        if run_source == RUN_SOURCE_TEMP:
            return await self._request_bytes("GET", f"/v1/temp-skill-runs/{request_id}/bundle")
        return await self._request_bytes("GET", f"/v1/jobs/{request_id}/bundle")

    async def stream_run_events(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        cursor: int = 0,
    ) -> AsyncIterator[bytes]:
        params = {"cursor": cursor}
        path = f"{self._run_base_path(request_id, run_source=run_source)}/events"
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, params=params) as response:
                if response.status_code >= 400:
                    detail = await _extract_error_detail(response)
                    raise BackendApiError(response.status_code, detail)
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

    async def get_run_event_history(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        from_seq: int | None = None,
        to_seq: int | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if from_seq is not None:
            params["from_seq"] = from_seq
        if to_seq is not None:
            params["to_seq"] = to_seq
        if from_ts:
            params["from_ts"] = from_ts
        if to_ts:
            params["to_ts"] = to_ts
        return await self._request_json(
            "GET",
            f"{self._run_base_path(request_id, run_source=run_source)}/events/history",
            params=params if params else None,
        )

    async def get_run_log_range(
        self,
        request_id: str,
        *,
        run_source: RunSource = RUN_SOURCE_INSTALLED,
        stream: str,
        byte_from: int = 0,
        byte_to: int = 0,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"{self._run_base_path(request_id, run_source=run_source)}/logs/range",
            params={
                "stream": stream,
                "byte_from": byte_from,
                "byte_to": byte_to,
            },
        )

    def _run_base_path(self, request_id: str, *, run_source: RunSource) -> str:
        if run_source == RUN_SOURCE_TEMP:
            return f"/v1/temp-skill-runs/{request_id}"
        return f"/v1/jobs/{request_id}"

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                json=json_payload,
                files=files,
                params=params,
            )
        if response.status_code >= 400:
            detail = _extract_error_detail_from_response(response)
            raise BackendApiError(response.status_code, detail)
        payload = response.json()
        if not isinstance(payload, dict):
            raise BackendApiError(502, "Backend returned non-object payload")
        return payload

    async def _request_bytes(
        self,
        method: str,
        path: str,
    ) -> bytes:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
            )
        if response.status_code >= 400:
            detail = _extract_error_detail_from_response(response)
            raise BackendApiError(response.status_code, detail)
        return response.content


def _extract_error_detail_from_response(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text
    if isinstance(payload, dict):
        detail = payload.get("detail")
        return detail if detail is not None else payload
    return payload


async def _extract_error_detail(response: httpx.Response) -> Any:
    raw = await response.aread()
    if not raw:
        return ""
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return payload
