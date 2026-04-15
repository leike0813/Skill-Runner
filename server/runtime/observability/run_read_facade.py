from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, StreamingResponse  # type: ignore[import-not-found]

from server.models import (
    CancelResponse,
    RunArtifactsResponse,
    RunFileEntry,
    RunFilePreviewResponse,
    RunFilesResponse,
    RunLogsResponse,
    RunResultResponse,
    RunStatus,
)
from server.runtime.observability.job_control_port import JobControlPort
from .run_observability import run_observability_service
from .run_source_adapter import (
    RunSourceAdapter,
    get_request_and_run_dir,
    installed_run_source_adapter,
)

TERMINAL_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}
ACTIVE_CANCELABLE_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_USER, RunStatus.WAITING_AUTH}

class _UnconfiguredJobControl:
    def build_run_bundle(self, run_dir: Path, debug: bool = False):
        _ = run_dir
        _ = debug
        raise RuntimeError("Run read facade job control port is not configured")

    async def cancel_run(self, **kwargs):
        _ = kwargs
        raise RuntimeError("Run read facade job control port is not configured")


job_control: Any = _UnconfiguredJobControl()


def configure_run_read_facade_ports(*, job_control_backend: Any) -> None:
    global job_control
    job_control = job_control_backend


class RunReadFacade:
    def _job_control(self) -> JobControlPort:
        return job_control

    async def _resolve_request_and_run_dir(
        self,
        *,
        source_adapter: RunSourceAdapter | None,
        request_id: str,
    ) -> tuple[dict[str, Any], Path]:
        resolved_source = source_adapter or installed_run_source_adapter
        return await get_request_and_run_dir(resolved_source, request_id)

    async def get_result(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> RunResultResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        current_status = _read_status(run_dir).value
        if current_status not in {RunStatus.SUCCEEDED.value, RunStatus.FAILED.value, RunStatus.CANCELED.value}:
            raise HTTPException(status_code=409, detail="terminal result not ready")
        result_path = run_dir / "result" / "result.json"
        if not result_path.exists():
            raise HTTPException(status_code=404, detail="Run result not found")

        with open(result_path, "r", encoding="utf-8") as f:
            result_payload = json.load(f)
        return RunResultResponse(request_id=request_id, result=result_payload)

    async def get_artifacts(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> RunArtifactsResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        result_path = run_dir / "result" / "result.json"
        artifacts: list[str] = []
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            artifacts_obj = payload.get("artifacts")
            if isinstance(artifacts_obj, list):
                artifacts = [
                    item.strip()
                    for item in artifacts_obj
                    if isinstance(item, str) and item.strip()
                ]
        return RunArtifactsResponse(request_id=request_id, artifacts=artifacts)

    async def _get_bundle_by_mode(
        self,
        *,
        source_adapter: RunSourceAdapter | None,
        request_id: str,
        debug: bool,
    ) -> FileResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        bundle_name = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        bundle_path = run_dir / "bundle" / bundle_name
        if not bundle_path.exists():
            control = self._job_control()
            if hasattr(control, "build_run_bundle"):
                control.build_run_bundle(run_dir, debug)
            else:
                # Backward-compatible fallback for legacy test doubles.
                legacy_control = control
                if isinstance(legacy_control, object):
                    getattr(legacy_control, "_build_run_bundle")(run_dir, debug)

        if not bundle_path.exists():
            raise HTTPException(status_code=404, detail="Bundle not found")
        return FileResponse(path=bundle_path, filename=bundle_path.name)

    async def get_bundle(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> FileResponse:
        return await self._get_bundle_by_mode(
            source_adapter=source_adapter,
            request_id=request_id,
            debug=False,
        )

    async def get_debug_bundle(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> FileResponse:
        return await self._get_bundle_by_mode(
            source_adapter=source_adapter,
            request_id=request_id,
            debug=True,
        )

    async def get_files(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> RunFilesResponse:
        _request_record, _run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        try:
            detail = await run_observability_service.get_run_detail(request_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        raw_entries = detail.get("entries")
        entries = raw_entries if isinstance(raw_entries, list) else []
        normalized_entries: list[RunFileEntry] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized_entries.append(
                RunFileEntry(
                    path=str(entry.get("rel_path") or ""),
                    name=str(entry.get("name") or ""),
                    is_dir=bool(entry.get("is_dir")),
                    depth=int(entry.get("depth") or 0),
                )
            )
        return RunFilesResponse(
            request_id=request_id,
            run_id=str(detail.get("run_id") or ""),
            entries=normalized_entries,
        )

    async def get_file_preview(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        path: str,
    ) -> RunFilePreviewResponse:
        _request_record, _run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        try:
            detail = await run_observability_service.get_run_detail(request_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        try:
            preview = await run_observability_service.build_run_file_preview(request_id, path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return RunFilePreviewResponse(
            request_id=request_id,
            run_id=str(detail.get("run_id") or ""),
            path=Path(path).as_posix(),
            preview=preview,
        )

    async def get_logs(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> RunLogsResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        latest_attempt = _latest_attempt_from_audit(run_dir)
        if latest_attempt <= 0:
            return RunLogsResponse(request_id=request_id)
        audit_dir = run_dir / ".audit"

        return RunLogsResponse(
            request_id=request_id,
            prompt=None,
            stdout=_read_log(audit_dir / f"stdout.{latest_attempt}.log"),
            stderr=_read_log(audit_dir / f"stderr.{latest_attempt}.log"),
        )

    async def stream_events(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        request: Request,
        cursor: int = 0,
    ) -> StreamingResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )

        async def _event_stream():
            async for item in run_observability_service.iter_sse_events(
                run_dir=run_dir,
                request_id=request_id,
                cursor=cursor,
                is_disconnected=request.is_disconnected,
            ):
                yield run_observability_service.format_sse_frame(
                    item["event"],
                    item["data"],
                )

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def stream_chat(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        request: Request,
        cursor: int = 0,
    ) -> StreamingResponse:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )

        async def _event_stream():
            async for item in run_observability_service.iter_chat_events(
                run_dir=run_dir,
                request_id=request_id,
                cursor=cursor,
                is_disconnected=request.is_disconnected,
            ):
                yield run_observability_service.format_sse_frame(
                    item["event"],
                    item["data"],
                )

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def list_event_history(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        from_seq: int | None,
        to_seq: int | None,
        from_ts: str | None,
        to_ts: str | None,
    ) -> dict[str, Any]:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        payload = await run_observability_service.get_event_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        events_obj = payload.get("events")
        events = events_obj if isinstance(events_obj, list) else []
        return {
            "request_id": request_id,
            "count": len(events),
            "events": events,
            "source": payload.get("source", "audit"),
            "cursor_floor": payload.get("cursor_floor", 0),
            "cursor_ceiling": payload.get("cursor_ceiling", 0),
        }

    async def list_chat_history(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        from_seq: int | None,
        to_seq: int | None,
        from_ts: str | None,
        to_ts: str | None,
    ) -> dict[str, Any]:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        payload = await run_observability_service.get_chat_history_payload(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        events_obj = payload.get("events")
        events = events_obj if isinstance(events_obj, list) else []
        return {
            "request_id": request_id,
            "count": len(events),
            "events": events,
            "source": payload.get("source", "audit"),
            "cursor_floor": payload.get("cursor_floor", 0),
            "cursor_ceiling": payload.get("cursor_ceiling", 0),
        }

    async def read_log_range(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
        stream: str,
        byte_from: int,
        byte_to: int,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        _request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=source_adapter,
            request_id=request_id,
        )
        if byte_to > 0 and byte_to < byte_from:
            raise HTTPException(status_code=400, detail="byte_to must be greater than or equal to byte_from")
        try:
            return await run_observability_service.read_log_range(
                run_dir=run_dir,
                request_id=request_id,
                stream=stream,
                byte_from=byte_from,
                byte_to=byte_to,
                attempt=attempt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    async def cancel_run(
        self,
        *,
        source_adapter: RunSourceAdapter | None = None,
        request_id: str,
    ) -> CancelResponse:
        resolved_source = source_adapter or installed_run_source_adapter
        request_record, run_dir = await self._resolve_request_and_run_dir(
            source_adapter=resolved_source,
            request_id=request_id,
        )
        run_id_obj = request_record.get("run_id")
        if not isinstance(run_id_obj, str) or not run_id_obj:
            raise HTTPException(status_code=404, detail="Run not found")
        run_id = run_id_obj

        status = _read_status(run_dir)
        if status in TERMINAL_STATUSES:
            return CancelResponse(
                request_id=request_id,
                run_id=run_id,
                status=status,
                accepted=False,
                message="Run already in terminal state",
            )
        if status not in ACTIVE_CANCELABLE_STATUSES:
            return CancelResponse(
                request_id=request_id,
                run_id=run_id,
                status=status,
                accepted=False,
                message="Run is not cancelable",
            )

        cancel_kwargs: dict[str, Any] = {
            "run_id": run_id,
            "engine_name": str(request_record.get("engine", "")),
            "run_dir": run_dir,
            "status": status,
        }
        cancel_kwargs.update(resolved_source.build_cancel_kwargs(request_id))
        accepted = await self._job_control().cancel_run(**cancel_kwargs)
        return CancelResponse(
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.CANCELED,
            accepted=accepted,
            message="Cancel request accepted" if accepted else "Cancel already requested",
        )


def _read_status(run_dir: Path) -> RunStatus:
    state_file = run_dir / ".state" / "state.json"
    if state_file.exists():
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        return RunStatus(payload.get("status", RunStatus.QUEUED.value))
    return RunStatus.QUEUED


def _read_log(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _latest_attempt_from_audit(run_dir: Path) -> int:
    audit_dir = run_dir / ".audit"
    if not audit_dir.exists() or not audit_dir.is_dir():
        return 0
    latest = 0
    for path in audit_dir.glob("meta.*.json"):
        parts = path.name.split(".")
        if len(parts) != 3:
            continue
        try:
            attempt = int(parts[1])
        except ValueError:
            continue
        if attempt > latest:
            latest = attempt
    return latest


run_read_facade = RunReadFacade()
