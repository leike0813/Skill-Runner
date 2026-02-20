import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request  # type: ignore[import-not-found]

from ..models import (
    CancelResponse,
    EngineModelInfo,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    ManagementEngineDetail,
    ManagementEngineListResponse,
    ManagementEngineSummary,
    ManagementRunConversationState,
    ManagementRunFilePreviewResponse,
    ManagementRunFilesResponse,
    ManagementRunListResponse,
    ManagementSkillDetail,
    ManagementSkillListResponse,
    ManagementSkillSchemasResponse,
    ManagementSkillSummary,
    RecoveryState,
    RunStatus,
    SkillManifest,
)
from ..services.agent_cli_manager import AgentCliManager
from ..services.model_registry import model_registry
from ..services.run_observability import run_observability_service
from ..services.run_store import run_store
from ..services.skill_browser import list_skill_entries, resolve_skill_file_path
from ..services.engine_policy import resolve_skill_engine_policy
from ..services.skill_registry import skill_registry
from . import jobs as jobs_router


router = APIRouter(prefix="/management", tags=["management"])
agent_cli_manager = AgentCliManager()


@router.get("/skills", response_model=ManagementSkillListResponse)
async def list_management_skills():
    skills = skill_registry.list_skills()
    return ManagementSkillListResponse(
        skills=[_build_skill_summary(skill) for skill in skills]
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
        input=_read_skill_schema_content(skill_root, schemas, "input"),
        parameter=_read_skill_schema_content(skill_root, schemas, "parameter"),
        output=_read_skill_schema_content(skill_root, schemas, "output"),
    )


@router.get("/engines", response_model=ManagementEngineListResponse)
async def list_management_engines():
    engine_rows = model_registry.list_engines()
    cli_versions: dict[str, str | None] = {
        str(item.get("engine")): item.get("cli_version_detected")
        for item in engine_rows
        if isinstance(item, dict) and isinstance(item.get("engine"), str)
    }
    auth_status = agent_cli_manager.collect_auth_status()

    engine_names = sorted(set(cli_versions.keys()) | set(auth_status.keys()))
    summaries: list[ManagementEngineSummary] = []
    for engine in engine_names:
        models_count = 0
        try:
            catalog = model_registry.get_models(engine)
            models_count = len(catalog.models)
            cli_version = catalog.cli_version_detected
        except Exception:
            cli_version = cli_versions.get(engine)

        auth_payload = auth_status.get(engine, {})
        auth_ready = bool(auth_payload.get("auth_ready"))
        summaries.append(
            ManagementEngineSummary(
                engine=engine,
                cli_version=cli_version,
                auth_ready=auth_ready,
                sandbox_status=_derive_sandbox_status(engine, auth_ready),
                models_count=models_count,
            )
        )

    return ManagementEngineListResponse(engines=summaries)


@router.get("/engines/{engine}", response_model=ManagementEngineDetail)
async def get_management_engine(engine: str):
    auth_status = agent_cli_manager.collect_auth_status().get(engine, {})
    try:
        catalog = model_registry.get_models(engine)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    models = [
        EngineModelInfo(
            id=entry.id,
            display_name=entry.display_name,
            deprecated=entry.deprecated,
            notes=entry.notes,
            supported_effort=entry.supported_effort,
        )
        for entry in catalog.models
    ]
    auth_ready = bool(auth_status.get("auth_ready"))
    return ManagementEngineDetail(
        engine=engine,
        cli_version=catalog.cli_version_detected,
        auth_ready=auth_ready,
        sandbox_status=_derive_sandbox_status(engine, auth_ready),
        models_count=len(models),
        models=models,
        upgrade_status={"state": "idle"},
        last_error=None,
    )


@router.get("/runs", response_model=ManagementRunListResponse)
async def list_management_runs(limit: int = Query(default=200, ge=1, le=1000)):
    rows = run_observability_service.list_runs(limit=limit)
    runs: list[ManagementRunConversationState] = []
    for row in rows:
        request_id_obj = row.get("request_id")
        run_id_obj = row.get("run_id")
        if not isinstance(request_id_obj, str) or not isinstance(run_id_obj, str):
            continue
        request_id = request_id_obj
        run_status = _parse_run_status(row.get("status"))
        pending_interaction_id = (
            _read_pending_interaction_id(request_id)
            if run_status == RunStatus.WAITING_USER
            else None
        )
        auto_stats = run_store.get_auto_decision_stats(request_id)
        runs.append(
            ManagementRunConversationState(
                request_id=request_id,
                run_id=run_id_obj,
                status=run_status,
                engine=str(row.get("engine", "unknown")),
                skill_id=str(row.get("skill_id", "unknown")),
                updated_at=_parse_datetime(row.get("updated_at")),
                pending_interaction_id=pending_interaction_id,
                interaction_count=run_store.get_interaction_count(request_id),
                auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
                last_auto_decision_at=_parse_datetime_or_none(auto_stats.get("last_auto_decision_at")),
                recovery_state=_parse_recovery_state(row.get("recovery_state")),
                recovered_at=_parse_datetime_or_none(row.get("recovered_at")),
                recovery_reason=_coerce_str_or_none(row.get("recovery_reason")),
                poll_logs=bool(row.get("status") in {"queued", "running"}),
                error=None,
            )
        )
    return ManagementRunListResponse(runs=runs)


@router.get("/runs/{request_id}", response_model=ManagementRunConversationState)
async def get_management_run(request_id: str):
    detail = _get_run_detail_or_404(request_id)
    return _build_run_state_from_detail(request_id, detail)


@router.get("/runs/{request_id}/files", response_model=ManagementRunFilesResponse)
async def get_management_run_files(request_id: str):
    detail = _get_run_detail_or_404(request_id)
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
    detail = _get_run_detail_or_404(request_id)
    try:
        preview = run_observability_service.build_run_file_preview(request_id, path)
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
    stdout_from: int = Query(default=0, ge=0),
    stderr_from: int = Query(default=0, ge=0),
):
    return await jobs_router.stream_run_events(
        request_id=request_id,
        request=request,
        stdout_from=stdout_from,
        stderr_from=stderr_from,
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
    if skill_path is None:
        issues.append("missing skill path")
    elif not skill_path.exists() or not skill_path.is_dir():
        issues.append("skill path not found")
    else:
        installed_at = datetime.fromtimestamp(skill_path.stat().st_mtime)
        runner_path = skill_path / "assets" / "runner.json"
        if not runner_path.exists():
            issues.append("missing assets/runner.json")
        schemas = _normalize_schemas(getattr(skill, "schemas", {}))
        for schema_name, schema_path in schemas.items():
            target = (skill_path / schema_path).resolve()
            if not target.exists():
                issues.append(f"missing schema: {schema_name}")
    return ManagementSkillSummary(
        id=str(getattr(skill, "id", "")),
        name=str(getattr(skill, "name", None) or getattr(skill, "id", "")),
        version=str(getattr(skill, "version", "")),
        engines=engine_policy.declared_engines,
        unsupported_engines=engine_policy.unsupported_engines,
        effective_engines=engine_policy.effective_engines,
        execution_modes=_normalize_execution_modes(getattr(skill, "execution_modes", [])),
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
    skill_root: Path,
    schemas: dict[str, str],
    schema_key: str,
) -> dict[str, Any] | None:
    schema_path = schemas.get(schema_key)
    if not schema_path:
        return None
    try:
        target = resolve_skill_file_path(skill_root, schema_path)
    except (ValueError, FileNotFoundError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {schema_key} schema",
        )
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {schema_key} schema",
        )
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {schema_key} schema",
        )
    return payload


def _derive_sandbox_status(engine: str, auth_ready: bool) -> str:
    if engine == "iflow":
        return "unsupported"
    if auth_ready:
        return "available"
    return "unknown"


def _get_run_detail_or_404(request_id: str) -> dict[str, Any]:
    try:
        return run_observability_service.get_run_detail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _build_run_state_from_detail(
    request_id: str,
    detail: dict[str, Any],
) -> ManagementRunConversationState:
    run_dir_obj = detail.get("run_dir")
    run_dir = Path(run_dir_obj) if isinstance(run_dir_obj, str) else None
    auto_stats = run_store.get_auto_decision_stats(request_id)
    status = _parse_run_status(detail.get("status"))
    return ManagementRunConversationState(
        request_id=request_id,
        run_id=str(detail.get("run_id", "")),
        status=status,
        engine=str(detail.get("engine", "unknown")),
        skill_id=str(detail.get("skill_id", "unknown")),
        updated_at=_parse_datetime(detail.get("updated_at")),
        pending_interaction_id=(
            _read_pending_interaction_id(request_id)
            if status == RunStatus.WAITING_USER
            else None
        ),
        interaction_count=run_store.get_interaction_count(request_id),
        auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
        last_auto_decision_at=_parse_datetime_or_none(auto_stats.get("last_auto_decision_at")),
        recovery_state=_parse_recovery_state(detail.get("recovery_state")),
        recovered_at=_parse_datetime_or_none(detail.get("recovered_at")),
        recovery_reason=_coerce_str_or_none(detail.get("recovery_reason")),
        poll_logs=bool(detail.get("poll_logs", False)),
        error=_read_run_error(run_dir),
    )


def _read_pending_interaction_id(request_id: str) -> int | None:
    pending = run_store.get_pending_interaction(request_id)
    if not isinstance(pending, dict):
        return None
    value = pending.get("interaction_id")
    if value is None:
        return None
    try:
        interaction_id = int(value)
    except Exception:
        return None
    if interaction_id <= 0:
        return None
    return interaction_id


def _read_run_error(run_dir: Path | None) -> Any:
    if not run_dir:
        return None
    status_file = run_dir / "status.json"
    if not status_file.exists():
        return None
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
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
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _parse_datetime_or_none(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw)
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
