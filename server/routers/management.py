import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile  # type: ignore[import-not-found]

from ..config import config
from ..logging_config import get_logging_settings_payload, reload_logging_from_settings
from ..models import (
    CancelResponse,
    EngineModelInfo,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    ManagementDataResetRequest,
    ManagementDataResetResponse,
    ManagementEngineDetail,
    ManagementEngineAuthImportSpecResponse,
    ManagementEngineAuthImportSubmitResponse,
    ManagementEngineListResponse,
    ManagementEngineSummary,
    ManagementSystemSettingsResponse,
    ManagementSystemLogQueryResponse,
    ManagementSystemSettingsUpdateRequest,
    ManagementRunConversationState,
    ManagementRunFilePreviewResponse,
    ManagementRunFilesResponse,
    ManagementRunListResponse,
    ManagementRuntimeOptionsResponse,
    ManagementSkillDetail,
    ManagementSkillListResponse,
    ManagementSkillRuntimeView,
    ManagementSkillSchemasResponse,
    ManagementSkillSummary,
    ManagementLoggingSettingsResponse,
    RecoveryState,
    RunStatus,
    SkillManifest,
)
from ..services.engine_management.model_registry import model_registry
from ..services.engine_management.auth_import_service import auth_import_service, AuthImportError
from ..services.engine_management.auth_import_validator_registry import AuthImportValidationError
from ..services.orchestration.runtime_observability_ports import install_runtime_observability_ports
from ..services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
from ..runtime.observability.run_observability import run_observability_service
from ..services.orchestration.run_store import run_store
from ..services.skill.skill_browser import list_skill_entries, resolve_skill_file_path
from ..services.skill.skill_asset_resolver import load_resolved_json, resolve_schema_asset
from ..services.engine_management.engine_policy import resolve_skill_engine_policy
from ..services.platform.data_reset_service import (
    DATA_RESET_CONFIRMATION_TEXT,
    DataResetBusyError,
    DataResetOptions,
    data_reset_service,
)
from ..services.platform.system_settings_service import (
    SystemSettingsValidationError,
    system_settings_service,
)
from ..services.platform.system_log_explorer_service import system_log_explorer_service
from ..services.skill.skill_registry import is_builtin_skill_path, skill_registry
from ..services.orchestration.workspace_manager import workspace_manager
from . import jobs as jobs_router


router = APIRouter(prefix="/management", tags=["management"])
logger = logging.getLogger(__name__)

install_runtime_protocol_ports()
install_runtime_observability_ports()


def _build_system_settings_response() -> ManagementSystemSettingsResponse:
    logging_payload = get_logging_settings_payload()
    logging_settings = ManagementLoggingSettingsResponse.model_validate(logging_payload)
    return ManagementSystemSettingsResponse(
        logging=logging_settings,
        engine_auth_session_log_persistence_enabled=bool(
            config.SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED
        ),
        reset_confirmation_text=DATA_RESET_CONFIRMATION_TEXT,
    )


@router.get("/system/settings", response_model=ManagementSystemSettingsResponse)
async def get_management_system_settings():
    try:
        return _build_system_settings_response()
    except (SystemSettingsValidationError, OSError, ValueError) as exc:
        logger.exception(
            "management.get_system_settings failed; returning HTTP 500",
            extra={
                "component": "router.management",
                "action": "get_system_settings",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/system/settings", response_model=ManagementSystemSettingsResponse)
async def update_management_system_settings(request: ManagementSystemSettingsUpdateRequest):
    try:
        system_settings_service.update_logging_settings(request.logging.model_dump())
        reload_logging_from_settings()
        return _build_system_settings_response()
    except SystemSettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        logger.exception(
            "management.update_system_settings failed; returning HTTP 500",
            extra={
                "component": "router.management",
                "action": "update_system_settings",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/system/reset-data", response_model=ManagementDataResetResponse)
async def reset_management_data(request: ManagementDataResetRequest):
    if request.confirmation.strip() != DATA_RESET_CONFIRMATION_TEXT:
        raise HTTPException(
            status_code=400,
            detail=f"confirmation must equal '{DATA_RESET_CONFIRMATION_TEXT}'",
        )
    options = DataResetOptions(
        include_logs=request.include_logs,
        include_engine_catalog=request.include_engine_catalog,
        include_engine_auth_sessions=(
            request.include_engine_auth_sessions
            and bool(config.SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED)
        ),
        dry_run=request.dry_run,
    )
    try:
        result = await asyncio.to_thread(data_reset_service.execute_reset, options)
    except DataResetBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except OSError as exc:
        logger.exception(
            "management.reset_data failed; returning HTTP 500",
            extra={
                "component": "router.management",
                "action": "reset_data",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))
    return ManagementDataResetResponse(**result.to_payload())


@router.get("/system/logs/query", response_model=ManagementSystemLogQueryResponse)
async def query_management_system_logs(
    source: str = Query(...),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    q: str | None = Query(default=None),
    level: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
):
    if source.strip().lower() not in {"system", "bootstrap"}:
        raise HTTPException(status_code=400, detail="source must be one of: system, bootstrap")
    normalized_level = level.strip().upper() if isinstance(level, str) and level.strip() else None
    if normalized_level and normalized_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise HTTPException(status_code=400, detail="level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    try:
        payload = await asyncio.to_thread(
            system_log_explorer_service.query,
            source=source,
            cursor=cursor,
            limit=limit,
            q=q,
            level=normalized_level,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        logger.exception(
            "management.query_system_logs failed; returning HTTP 500",
            extra={
                "component": "router.management",
                "action": "query_system_logs",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))
    return ManagementSystemLogQueryResponse(**payload)


@router.get("/skills", response_model=ManagementSkillListResponse)
async def list_management_skills():
    skills = skill_registry.list_skills()
    return ManagementSkillListResponse(
        skills=[_build_skill_summary(skill) for skill in skills]
    )


@router.get("/runtime-options", response_model=ManagementRuntimeOptionsResponse)
async def get_management_runtime_options():
    return ManagementRuntimeOptionsResponse(
        service_defaults={
            "hard_timeout_seconds": int(config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS),
        }
    )


@router.get("/skills/{skill_id}", response_model=ManagementSkillDetail)
async def get_management_skill(skill_id: str):
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.path:
        raise HTTPException(status_code=404, detail="Skill path not found")

    skill_root = Path(skill.path)
    if not skill_root.exists() or not skill_root.is_dir():
        raise HTTPException(status_code=404, detail="Skill path not found")

    summary = _build_skill_summary(skill)
    return ManagementSkillDetail(
        **summary.model_dump(),
        runtime=_build_skill_runtime(skill),
        schemas=_normalize_schemas(skill.schemas),
        entrypoints=skill.entrypoint if isinstance(skill.entrypoint, dict) else {},
        files=list_skill_entries(skill_root),
    )


@router.get("/skills/{skill_id}/schemas", response_model=ManagementSkillSchemasResponse)
async def get_management_skill_schemas(skill_id: str):
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.path:
        raise HTTPException(status_code=404, detail="Skill path not found")

    skill_root = Path(skill.path)
    if not skill_root.exists() or not skill_root.is_dir():
        raise HTTPException(status_code=404, detail="Skill path not found")

    schemas = _normalize_schemas(skill.schemas)
    return ManagementSkillSchemasResponse(
        skill_id=skill_id,
        input=_read_skill_schema_content(skill, "input"),
        parameter=_read_skill_schema_content(skill, "parameter"),
        output=_read_skill_schema_content(skill, "output"),
    )


@router.get("/engines", response_model=ManagementEngineListResponse)
async def list_management_engines():
    engine_rows = model_registry.list_engines()
    cli_versions: dict[str, str | None] = {
        str(item.get("engine")): item.get("cli_version_detected")
        for item in engine_rows
        if isinstance(item, dict) and isinstance(item.get("engine"), str)
    }
    engine_names = sorted(cli_versions.keys())
    summaries: list[ManagementEngineSummary] = []
    for engine in engine_names:
        models_count = 0
        try:
            catalog = model_registry.get_models(engine)
            models_count = len(catalog.models)
            cli_version = catalog.cli_version_detected
        except (ValueError, RuntimeError, OSError) as exc:
            # Boundary fallback: model discovery is best-effort for list view.
            logger.exception(
                "management.list_engines model discovery fallback",
                extra={
                    "component": "router.management",
                    "action": "list_engines.get_models",
                    "engine": engine,
                    "error_type": type(exc).__name__,
                    "fallback": "use_cli_version_snapshot",
                },
            )
            cli_version = cli_versions.get(engine)

        summaries.append(
            ManagementEngineSummary(
                engine=engine,
                cli_version=cli_version,
                models_count=models_count,
            )
        )

    return ManagementEngineListResponse(engines=summaries)


@router.get("/engines/{engine}", response_model=ManagementEngineDetail)
async def get_management_engine(engine: str):
    try:
        catalog = model_registry.get_models(engine)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    models = [
        EngineModelInfo(
            id=entry.id,
            display_name=entry.display_name,
            deprecated=entry.deprecated,
            notes=entry.notes,
            supported_effort=entry.supported_effort,
            provider=entry.provider,
            model=entry.model,
        )
        for entry in catalog.models
    ]
    return ManagementEngineDetail(
        engine=engine,
        cli_version=catalog.cli_version_detected,
        models_count=len(models),
        models=models,
        upgrade_status={"state": "idle"},
        last_error=None,
    )


@router.get(
    "/engines/{engine}/auth/import/spec",
    response_model=ManagementEngineAuthImportSpecResponse,
)
async def get_management_engine_auth_import_spec(
    engine: str,
    provider_id: str | None = Query(default=None),
):
    try:
        payload = auth_import_service.get_import_spec(
            engine=engine,
            provider_id=provider_id,
        )
    except (AuthImportError, AuthImportValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ManagementEngineAuthImportSpecResponse(**payload)


@router.post(
    "/engines/{engine}/auth/import",
    response_model=ManagementEngineAuthImportSubmitResponse,
)
async def submit_management_engine_auth_import(
    engine: str,
    provider_id: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    uploaded: dict[str, bytes] = {}
    for item in files:
        filename = Path(item.filename or "").name.strip()
        if not filename:
            continue
        uploaded[filename] = await item.read()
    try:
        payload = auth_import_service.import_auth_files(
            engine=engine,
            provider_id=provider_id,
            files=uploaded,
        )
    except (AuthImportError, AuthImportValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ManagementEngineAuthImportSubmitResponse(**payload)


@router.get("/runs", response_model=ManagementRunListResponse)
async def list_management_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=1000),
):
    paging_payload: dict[str, Any]
    if limit is not None:
        listed_rows = await run_observability_service.list_runs(limit=limit)
        paging_payload = {
            "runs": listed_rows,
            "page": 1,
            "page_size": limit,
            "total": len(listed_rows),
            "total_pages": 1 if listed_rows else 0,
        }
    else:
        paging_payload = await run_observability_service.list_runs_paginated(
            page=page,
            page_size=page_size,
        )
    rows_obj = paging_payload.get("runs")
    rows: list[dict[str, Any]] = []
    if isinstance(rows_obj, list):
        for item in rows_obj:
            if isinstance(item, dict):
                rows.append(item)
    runs: list[ManagementRunConversationState] = []
    for row in rows:
        request_id_obj = row.get("request_id")
        run_id_obj = row.get("run_id")
        if not isinstance(request_id_obj, str) or not isinstance(run_id_obj, str):
            continue
        request_id = request_id_obj
        run_status = _parse_run_status(row.get("status"))
        pending_interaction_id = (
            await _read_pending_interaction_id(request_id)
            if run_status == RunStatus.WAITING_USER
            else None
        )
        auto_stats = await run_store.get_auto_decision_stats(request_id)
        runs.append(
            ManagementRunConversationState(
                request_id=request_id,
                run_id=run_id_obj,
                status=run_status,
                engine=str(row.get("engine", "unknown")),
                model=_coerce_str_or_none(row.get("model")),
                skill_id=str(row.get("skill_id", "unknown")),
                updated_at=_parse_datetime(row.get("updated_at")),
                pending_interaction_id=pending_interaction_id,
                interaction_count=await run_store.get_interaction_count(request_id),
                auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
                last_auto_decision_at=_parse_datetime_or_none(auto_stats.get("last_auto_decision_at")),
                recovery_state=_parse_recovery_state(row.get("recovery_state")),
                recovered_at=_parse_datetime_or_none(row.get("recovered_at")),
                recovery_reason=_coerce_str_or_none(row.get("recovery_reason")),
                poll_logs=bool(row.get("status") in {"queued", "running"}),
                error=None,
            )
        )
    return ManagementRunListResponse(
        runs=runs,
        page=_coerce_int_or_default(paging_payload.get("page"), 1),
        page_size=_coerce_int_or_default(paging_payload.get("page_size"), 20),
        total=_coerce_int_or_default(paging_payload.get("total"), 0),
        total_pages=_coerce_int_or_default(paging_payload.get("total_pages"), 0),
    )


@router.get("/runs/{request_id}", response_model=ManagementRunConversationState)
async def get_management_run(request_id: str):
    detail = await _get_run_detail_or_404(request_id)
    return await _build_run_state_from_detail(request_id, detail)


@router.get("/runs/{request_id}/files", response_model=ManagementRunFilesResponse)
async def get_management_run_files(request_id: str):
    detail = await _get_run_detail_or_404(request_id)
    return ManagementRunFilesResponse(
        request_id=request_id,
        run_id=str(detail.get("run_id", "")),
        entries=detail.get("entries", []),
    )


@router.get("/runs/{request_id}/file", response_model=ManagementRunFilePreviewResponse)
async def get_management_run_file(
    request_id: str,
    path: str = Query(..., min_length=1),
):
    detail = await _get_run_detail_or_404(request_id)
    try:
        preview = await run_observability_service.build_run_file_preview(request_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ManagementRunFilePreviewResponse(
        request_id=request_id,
        run_id=str(detail.get("run_id", "")),
        path=Path(path).as_posix(),
        preview=preview,
    )


@router.get("/runs/{request_id}/events")
async def stream_management_run_events(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await jobs_router.stream_run_events(
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/runs/{request_id}/events/history")
async def list_management_run_event_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await jobs_router.list_run_event_history(
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/runs/{request_id}/chat")
async def stream_management_run_chat(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await jobs_router.stream_run_chat(
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/runs/{request_id}/chat/history")
async def list_management_run_chat_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await jobs_router.list_run_chat_history(
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/runs/{request_id}/protocol/history")
async def list_management_run_protocol_history(
    request_id: str,
    stream: str = Query(...),
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
    attempt: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=200, ge=1, le=1000),
):
    request_record = await run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id_obj)
    if not run_dir or not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run directory not found")

    normalized_stream = stream.strip().lower()
    if normalized_stream not in {"fcmp", "rasp", "orchestrator"}:
        raise HTTPException(status_code=400, detail="stream must be one of: fcmp, rasp, orchestrator")

    try:
        payload = await run_observability_service.list_protocol_history(
            run_dir=run_dir,
            request_id=request_id,
            stream=normalized_stream,
            from_seq=from_seq,
            to_seq=to_seq,
            from_ts=from_ts,
            to_ts=to_ts,
            attempt=attempt,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if isinstance(payload, dict):
        rows_obj = payload.get("events")
        rows = rows_obj if isinstance(rows_obj, list) else []
        payload_attempt = payload.get("attempt")
        payload_attempts = payload.get("available_attempts") or []
    elif isinstance(payload, list):
        rows = payload
        payload_attempt = attempt
        payload_attempts = [attempt] if attempt is not None else []
    else:
        rows = []
        payload_attempt = attempt
        payload_attempts = [attempt] if attempt is not None else []
    return {
        "request_id": request_id,
        "stream": normalized_stream,
        "attempt": payload_attempt,
        "available_attempts": payload_attempts,
        "count": len(rows),
        "events": rows,
    }


@router.get("/runs/{request_id}/timeline/history")
async def list_management_run_timeline_history(
    request_id: str,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    request_record = await run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id_obj)
    if not run_dir or not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run directory not found")

    payload = await run_observability_service.list_timeline_history(
        run_dir=run_dir,
        request_id=request_id,
        cursor=cursor,
        limit=limit,
    )
    events_obj = payload.get("events")
    events = events_obj if isinstance(events_obj, list) else []
    return {
        "request_id": request_id,
        "count": len(events),
        "events": events,
        "cursor_floor": int(payload.get("cursor_floor") or 0),
        "cursor_ceiling": int(payload.get("cursor_ceiling") or 0),
        "source": payload.get("source") or "mixed",
    }


@router.post("/runs/{request_id}/protocol/rebuild")
async def rebuild_management_run_protocol_history(request_id: str):
    request_record = await run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id_obj)
    if not run_dir or not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run directory not found")
    detail = await _get_run_detail_or_404(request_id)
    status_raw = detail.get("status")
    status_value = (
        status_raw.value
        if isinstance(status_raw, RunStatus)
        else str(status_raw or "").strip().lower()
    )
    if status_value not in {RunStatus.SUCCEEDED.value, RunStatus.FAILED.value, RunStatus.CANCELED.value}:
        raise HTTPException(status_code=409, detail="Protocol rebuild is only allowed for terminal runs")
    payload = await run_observability_service.rebuild_protocol_history(
        run_dir=run_dir,
        request_id=request_id,
    )
    return payload


@router.get("/runs/{request_id}/logs/range")
async def get_management_run_log_range(
    request_id: str,
    stream: str = Query(...),
    byte_from: int = Query(default=0, ge=0),
    byte_to: int = Query(default=0, ge=0),
    attempt: int | None = Query(default=None, ge=1),
):
    if attempt is None:
        return await jobs_router.get_run_log_range(
            request_id=request_id,
            stream=stream,
            byte_from=byte_from,
            byte_to=byte_to,
        )
    return await jobs_router.get_run_log_range(
        request_id=request_id,
        stream=stream,
        byte_from=byte_from,
        byte_to=byte_to,
        attempt=attempt,
    )


@router.get("/runs/{request_id}/pending", response_model=InteractionPendingResponse)
async def get_management_run_pending(request_id: str):
    return await jobs_router.get_interaction_pending(request_id)


@router.post("/runs/{request_id}/reply", response_model=InteractionReplyResponse)
async def reply_management_run(
    request_id: str,
    request: InteractionReplyRequest,
    background_tasks: BackgroundTasks,
):
    return await jobs_router.reply_interaction(request_id, request, background_tasks)


@router.post("/runs/{request_id}/cancel", response_model=CancelResponse)
async def cancel_management_run(request_id: str):
    return await jobs_router.cancel_run(request_id)


def _build_skill_summary(skill: SkillManifest) -> ManagementSkillSummary:
    issues: list[str] = []
    engine_policy = resolve_skill_engine_policy(skill)
    installed_at: datetime | None = None
    skill_path_raw = getattr(skill, "path", None)
    skill_path = Path(skill_path_raw) if skill_path_raw else None
    is_builtin = is_builtin_skill_path(skill_path)
    if skill_path is None:
        issues.append("missing skill path")
    elif not skill_path.exists() or not skill_path.is_dir():
        issues.append("skill path not found")
    else:
        installed_at = datetime.fromtimestamp(skill_path.stat().st_mtime)
        runner_path = skill_path / "assets" / "runner.json"
        if not runner_path.exists():
            issues.append("missing assets/runner.json")
        for schema_name in ("input", "parameter", "output"):
            resolution = resolve_schema_asset(skill, schema_name)
            if resolution.path is None:
                issues.append(f"missing schema: {schema_name}")
    return ManagementSkillSummary(
        id=str(getattr(skill, "id", "")),
        name=str(getattr(skill, "name", None) or getattr(skill, "id", "")),
        description=(
            str(getattr(skill, "description", "")).strip()
            if getattr(skill, "description", None) is not None
            else None
        ) or None,
        version=str(getattr(skill, "version", "")),
        engines=engine_policy.declared_engines,
        unsupported_engines=engine_policy.unsupported_engines,
        effective_engines=engine_policy.effective_engines,
        execution_modes=_normalize_execution_modes(getattr(skill, "execution_modes", [])),
        is_builtin=is_builtin,
        installed_at=installed_at,
        health="healthy" if not issues else "degraded",
        health_error="; ".join(issues) if issues else None,
    )


def _normalize_schemas(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str):
            normalized[key] = value
    return normalized


def _build_skill_runtime(skill: SkillManifest) -> ManagementSkillRuntimeView:
    runtime_obj = getattr(skill, "runtime", None)
    if runtime_obj is None:
        return ManagementSkillRuntimeView()
    default_options = getattr(runtime_obj, "default_options", None)
    if not isinstance(default_options, dict):
        return ManagementSkillRuntimeView()
    normalized = {
        str(key): value
        for key, value in default_options.items()
        if isinstance(key, str)
    }
    return ManagementSkillRuntimeView(default_options=normalized)


def _normalize_execution_modes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return ["auto"]
    normalized: list[str] = []
    for item in raw:
        value = getattr(item, "value", item)
        if isinstance(value, str):
            mode = value.strip()
            if mode:
                normalized.append(mode)
    if not normalized:
        return ["auto"]
    deduped = list(dict.fromkeys(normalized))
    return deduped


def _read_skill_schema_content(
    skill: SkillManifest,
    schema_key: str,
) -> dict[str, Any] | None:
    resolution = resolve_schema_asset(skill, schema_key)
    if resolution.path is None:
        if resolution.issue_source == "declared":
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {schema_key} schema",
            )
        return None
    payload = load_resolved_json(resolution.path)
    if payload is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {schema_key} schema",
        )
    return payload


async def _get_run_detail_or_404(request_id: str) -> dict[str, Any]:
    try:
        return await run_observability_service.get_run_detail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


async def _build_run_state_from_detail(
    request_id: str,
    detail: dict[str, Any],
) -> ManagementRunConversationState:
    run_dir_obj = detail.get("run_dir")
    run_dir = Path(run_dir_obj) if isinstance(run_dir_obj, str) else None
    auto_stats = await run_store.get_auto_decision_stats(request_id)
    status = _parse_run_status(detail.get("status"))
    timeout_obj = detail.get("interactive_reply_timeout_sec")
    timeout_sec = timeout_obj if isinstance(timeout_obj, int) and timeout_obj >= 0 else None
    return ManagementRunConversationState(
        request_id=request_id,
        run_id=str(detail.get("run_id", "")),
        status=status,
        engine=str(detail.get("engine", "unknown")),
        model=_coerce_str_or_none(detail.get("model")),
        skill_id=str(detail.get("skill_id", "unknown")),
        updated_at=_parse_datetime(detail.get("updated_at")),
        pending_interaction_id=(
            await _read_pending_interaction_id(request_id)
            if status == RunStatus.WAITING_USER
            else None
        ),
        interaction_count=await run_store.get_interaction_count(request_id),
        auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
        last_auto_decision_at=_parse_datetime_or_none(auto_stats.get("last_auto_decision_at")),
        recovery_state=_parse_recovery_state(detail.get("recovery_state")),
        recovered_at=_parse_datetime_or_none(detail.get("recovered_at")),
        recovery_reason=_coerce_str_or_none(detail.get("recovery_reason")),
        poll_logs=bool(detail.get("poll_logs", False)),
        error=_read_run_error(run_dir),
        interactive_auto_reply=(
            detail.get("interactive_auto_reply")
            if isinstance(detail.get("interactive_auto_reply"), bool)
            else None
        ),
        interactive_reply_timeout_sec=timeout_sec,
    )


async def _read_pending_interaction_id(request_id: str) -> int | None:
    pending = await run_store.get_pending_interaction(request_id)
    if not isinstance(pending, dict):
        return None
    value = pending.get("interaction_id")
    if value is None:
        return None
    try:
        interaction_id = int(value)
    except (TypeError, ValueError):
        return None
    if interaction_id <= 0:
        return None
    return interaction_id


def _read_run_error(run_dir: Path | None) -> Any:
    if not run_dir:
        return None
    state_file = run_dir / ".state" / "state.json"
    if not state_file.exists():
        return None
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload.get("error")


def _parse_run_status(raw: Any) -> RunStatus:
    if isinstance(raw, RunStatus):
        return raw
    if isinstance(raw, str):
        try:
            return RunStatus(raw)
        except ValueError:
            return RunStatus.QUEUED
    return RunStatus.QUEUED


def _parse_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _parse_datetime_or_none(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _coerce_str_or_none(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    return str(raw)


def _parse_recovery_state(raw: Any) -> RecoveryState:
    if isinstance(raw, RecoveryState):
        return raw
    if isinstance(raw, str):
        try:
            return RecoveryState(raw)
        except ValueError:
            return RecoveryState.NONE
    return RecoveryState.NONE


def _coerce_int_or_default(raw: Any, default: int) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return default
    return default
