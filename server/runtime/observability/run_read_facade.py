from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, StreamingResponse  # type: ignore[import-not-found]

from server.models import CancelResponse, RunArtifactsResponse, RunLogsResponse, RunResultResponse, RunStatus
from .run_observability import run_observability_service
from .run_source_adapter import RunSourceAdapter, get_request_and_run_dir, require_capability

TERMINAL_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}
ACTIVE_CANCELABLE_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_USER}

class _UnconfiguredJobControl:
    def _build_run_bundle(self, run_dir: Path, debug: bool = False):
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
    def _job_control(self) -> Any:
        return job_control

    def get_result(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
    ) -> RunResultResponse:
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        result_path = run_dir / "result" / "result.json"
        if not result_path.exists():
            raise HTTPException(status_code=404, detail="Run result not found")

        with open(result_path, "r", encoding="utf-8") as f:
            result_payload = json.load(f)
        return RunResultResponse(request_id=request_id, result=result_payload)

    def get_artifacts(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
    ) -> RunArtifactsResponse:
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        artifacts_dir = run_dir / "artifacts"
        artifacts: list[str] = []
        if artifacts_dir.exists():
            for path in artifacts_dir.rglob("*"):
                if path.is_file():
                    artifacts.append(path.relative_to(run_dir).as_posix())
        return RunArtifactsResponse(request_id=request_id, artifacts=artifacts)

    def get_bundle(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
    ) -> FileResponse:
        request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        debug_mode = bool(request_record.get("runtime_options", {}).get("debug"))
        bundle_name = "run_bundle_debug.zip" if debug_mode else "run_bundle.zip"
        bundle_path = run_dir / "bundle" / bundle_name
        if not bundle_path.exists():
            self._job_control()._build_run_bundle(run_dir, debug_mode)

        if not bundle_path.exists():
            raise HTTPException(status_code=404, detail="Bundle not found")
        return FileResponse(path=bundle_path, filename=bundle_path.name)

    def get_artifact_file(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        artifact_path: str,
    ) -> FileResponse:
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        if not artifact_path:
            raise HTTPException(status_code=400, detail="Artifact path is required")
        if not artifact_path.startswith("artifacts/"):
            raise HTTPException(status_code=404, detail="Artifact not found")
        target = (run_dir / artifact_path).resolve()
        artifacts_root = (run_dir / "artifacts").resolve()
        if not str(target).startswith(str(artifacts_root)):
            raise HTTPException(status_code=400, detail="Invalid artifact path")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path=target, filename=target.name)

    def get_logs(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
    ) -> RunLogsResponse:
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
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
        source_adapter: RunSourceAdapter,
        request_id: str,
        request: Request,
        cursor: int = 0,
    ) -> StreamingResponse:
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)

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

    def list_event_history(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        from_seq: int | None,
        to_seq: int | None,
        from_ts: str | None,
        to_ts: str | None,
    ) -> dict[str, Any]:
        require_capability(source_adapter, capability="supports_event_history")
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        events = run_observability_service.list_event_history(
            run_dir=run_dir,
            request_id=request_id,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        return {"request_id": request_id, "count": len(events), "events": events}

    def read_log_range(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        stream: str,
        byte_from: int,
        byte_to: int,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        require_capability(source_adapter, capability="supports_log_range")
        _request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        if byte_to > 0 and byte_to < byte_from:
            raise HTTPException(status_code=400, detail="byte_to must be greater than or equal to byte_from")
        try:
            return run_observability_service.read_log_range(
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
        source_adapter: RunSourceAdapter,
        request_id: str,
    ) -> CancelResponse:
        request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
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

        accepted = await self._job_control().cancel_run(
            run_id=run_id,
            engine_name=str(request_record.get("engine", "")),
            run_dir=run_dir,
            status=status,
            **source_adapter.build_cancel_kwargs(request_id),
        )
        return CancelResponse(
            request_id=request_id,
            run_id=run_id,
            status=RunStatus.CANCELED,
            accepted=accepted,
            message="Cancel request accepted" if accepted else "Cancel already requested",
        )


def _read_status(run_dir: Path) -> RunStatus:
    status_file = run_dir / "status.json"
    if not status_file.exists():
        return RunStatus.QUEUED
    payload = json.loads(status_file.read_text(encoding="utf-8"))
    return RunStatus(payload.get("status", RunStatus.QUEUED.value))


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
        except Exception:
            continue
        if attempt > latest:
            latest = attempt
    return latest


run_read_facade = RunReadFacade()
