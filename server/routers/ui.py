import uuid
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import (  # type: ignore[import-not-found]
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse  # type: ignore[import-not-found]
from fastapi.templating import Jinja2Templates  # type: ignore[import-not-found]

from ..models import EngineUpgradeTaskStatus, SkillInstallStatus
from ..services.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeValidationError,
    engine_upgrade_manager,
)
from ..services.model_registry import model_registry
from ..services.agent_cli_manager import AgentCliManager
from ..services.skill_browser import (
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)
from ..services.run_observability import run_observability_service
from ..services.skill_install_store import skill_install_store
from ..services.skill_package_manager import skill_package_manager
from ..services.skill_registry import skill_registry
from ..services.ui_auth import require_ui_basic_auth


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))


router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    dependencies=[Depends(require_ui_basic_auth)],
)
agent_cli_manager = AgentCliManager()


def _render_skills_table(request: Request, highlight_skill_id: str | None = None) -> HTMLResponse:
    skills = skill_registry.list_skills()
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/skills_table.html",
        context={
            "skills": skills,
            "highlight_skill_id": highlight_skill_id,
        },
    )


def _render_engine_upgrade_status(
    request: Request,
    request_id: str,
    status: str,
    results: dict,
    error: str | None,
    poll: bool,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/engine_upgrade_status.html",
        context={
            "request_id": request_id,
            "status": status,
            "results": results,
            "error": error,
            "poll": poll,
        },
    )


@router.get("", response_class=HTMLResponse)
async def ui_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ui/index.html",
        context={},
    )


@router.get("/skills/table", response_class=HTMLResponse)
async def ui_skills_table(request: Request, highlight_skill_id: str | None = None):
    return _render_skills_table(request, highlight_skill_id)


@router.get("/skills/{skill_id}", response_class=HTMLResponse)
async def ui_skill_detail(request: Request, skill_id: str):
    skill = skill_registry.get_skill(skill_id)
    if not skill or not skill.path:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill_root = Path(skill.path)
    if not skill_root.exists() or not skill_root.is_dir():
        raise HTTPException(status_code=404, detail="Skill path not found")

    entries = list_skill_entries(skill_root)
    return templates.TemplateResponse(
        request=request,
        name="ui/skill_detail.html",
        context={
            "skill": skill,
            "entries": entries,
        },
    )


@router.get("/skills/{skill_id}/view", response_class=HTMLResponse)
async def ui_skill_view_file(request: Request, skill_id: str, path: str):
    skill = skill_registry.get_skill(skill_id)
    if not skill or not skill.path:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill_root = Path(skill.path)
    if not skill_root.exists() or not skill_root.is_dir():
        raise HTTPException(status_code=404, detail="Skill path not found")

    try:
        file_path = resolve_skill_file_path(skill_root, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    preview = build_preview_payload(file_path)
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/file_preview.html",
        context={
            "skill_id": skill_id,
            "relative_path": Path(path).as_posix(),
            "preview": preview,
        },
    )


@router.get("/runs", response_class=HTMLResponse)
async def ui_runs(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ui/runs.html",
        context={},
    )


@router.get("/runs/table", response_class=HTMLResponse)
async def ui_runs_table(request: Request):
    runs = run_observability_service.list_runs(limit=200)
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/runs_table.html",
        context={"runs": runs},
    )


@router.get("/runs/{request_id}", response_class=HTMLResponse)
async def ui_run_detail(request: Request, request_id: str):
    try:
        detail = run_observability_service.get_run_detail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return templates.TemplateResponse(
        request=request,
        name="ui/run_detail.html",
        context={"detail": detail},
    )


@router.get("/runs/{request_id}/view", response_class=HTMLResponse)
async def ui_run_view_file(request: Request, request_id: str, path: str):
    try:
        preview = run_observability_service.build_run_file_preview(request_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return templates.TemplateResponse(
        request=request,
        name="ui/partials/file_preview.html",
        context={
            "relative_path": Path(path).as_posix(),
            "preview": preview,
        },
    )


@router.get("/runs/{request_id}/logs/tail", response_class=HTMLResponse)
async def ui_run_logs_tail(request: Request, request_id: str):
    try:
        payload = run_observability_service.get_logs_tail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/run_logs_tail.html",
        context={"payload": payload},
    )


@router.get("/engines", response_class=HTMLResponse)
async def ui_engines(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ui/engines.html",
        context={},
    )


@router.get("/engines/table", response_class=HTMLResponse)
async def ui_engines_table(request: Request):
    engines = model_registry.list_engines()
    auth_status = agent_cli_manager.collect_auth_status()
    rows = []
    seen_engines = set()
    for item in engines:
        engine_name_obj = item.get("engine")
        if not isinstance(engine_name_obj, str):
            continue
        engine_name = engine_name_obj
        seen_engines.add(engine_name)
        rows.append(
            {
                "engine": engine_name,
                "cli_version_detected": item.get("cli_version_detected"),
                "auth": auth_status.get(
                    engine_name,
                    {
                        "managed_present": False,
                        "effective_path_source": "missing",
                        "effective_cli_path": None,
                        "auth_ready": False,
                        "credential_files": {},
                    },
                ),
            }
        )
    for engine_name, auth_payload in auth_status.items():
        if engine_name in seen_engines:
            continue
        rows.append(
            {
                "engine": engine_name,
                "cli_version_detected": None,
                "auth": auth_payload,
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/engines_table.html",
        context={"rows": rows},
    )


@router.post("/engines/upgrades", response_class=HTMLResponse)
async def ui_create_engine_upgrade(
    request: Request,
    mode: str = Form(...),
    engine: str | None = Form(None),
):
    try:
        request_id = engine_upgrade_manager.create_task(mode, engine)
    except EngineUpgradeBusyError as exc:
        return _render_engine_upgrade_status(
            request=request,
            request_id="-",
            status=EngineUpgradeTaskStatus.FAILED.value,
            results={},
            error=str(exc),
            poll=False,
        )
    except EngineUpgradeValidationError as exc:
        return _render_engine_upgrade_status(
            request=request,
            request_id="-",
            status=EngineUpgradeTaskStatus.FAILED.value,
            results={},
            error=str(exc),
            poll=False,
        )

    return _render_engine_upgrade_status(
        request=request,
        request_id=request_id,
        status=EngineUpgradeTaskStatus.QUEUED.value,
        results={},
        error=None,
        poll=True,
    )


@router.get("/engines/upgrades/{request_id}/status", response_class=HTMLResponse)
async def ui_engine_upgrade_status(request: Request, request_id: str):
    record = engine_upgrade_manager.get_task(request_id)
    if not record:
        return _render_engine_upgrade_status(
            request=request,
            request_id=request_id,
            status=EngineUpgradeTaskStatus.FAILED.value,
            results={},
            error="Upgrade request not found",
            poll=False,
        )
    status = str(record.get("status", EngineUpgradeTaskStatus.FAILED.value))
    results_obj = record.get("results")
    results = results_obj if isinstance(results_obj, dict) else {}
    poll = status in {EngineUpgradeTaskStatus.QUEUED.value, EngineUpgradeTaskStatus.RUNNING.value}
    return _render_engine_upgrade_status(
        request=request,
        request_id=request_id,
        status=status,
        results=results,
        error=None,
        poll=poll,
    )


@router.get("/engines/{engine}/models", response_class=HTMLResponse)
async def ui_engine_models(request: Request, engine: str, error: str | None = None, message: str | None = None):
    try:
        view = model_registry.get_manifest_view(engine)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return templates.TemplateResponse(
        request=request,
        name="ui/engine_models.html",
        context={
            "engine": engine,
            "view": view,
            "error": error,
            "message": message,
        },
    )


@router.post("/engines/{engine}/models/snapshots")
async def ui_engine_models_add_snapshot(
    request: Request,
    engine: str,
    id: list[str] = Form(...),
    display_name: list[str] | None = Form(None),
    deprecated: list[str] | None = Form(None),
    notes: list[str] | None = Form(None),
    supported_effort: list[str] | None = Form(None),
):
    display_name = display_name or []
    deprecated = deprecated or []
    notes = notes or []
    supported_effort = supported_effort or []
    models = []
    for index, model_id in enumerate(id):
        model_id_clean = model_id.strip()
        if not model_id_clean:
            continue
        display_value = display_name[index].strip() if index < len(display_name) else ""
        notes_value = notes[index].strip() if index < len(notes) else ""
        deprecated_raw = deprecated[index].strip().lower() if index < len(deprecated) else "false"
        effort_raw = supported_effort[index].strip() if index < len(supported_effort) else ""
        efforts = [item.strip() for item in effort_raw.split(",") if item.strip()] if effort_raw else None
        models.append(
            {
                "id": model_id_clean,
                "display_name": display_value or None,
                "deprecated": deprecated_raw in {"1", "true", "yes", "on"},
                "notes": notes_value or None,
                "supported_effort": efforts,
            }
        )

    if not models:
        return RedirectResponse(
            url=f"/ui/engines/{engine}/models?error=No+valid+model+rows+submitted",
            status_code=303,
        )

    try:
        model_registry.add_snapshot_for_detected_version(engine, models)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/ui/engines/{engine}/models?error={quote_plus(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/engines/{engine}/models?message=Snapshot+created",
        status_code=303,
    )


@router.post("/skill-packages/install", response_class=HTMLResponse)
async def ui_install_skill_package(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded package is empty")

    request_id = str(uuid.uuid4())
    skill_package_manager.create_install_request(request_id, payload)
    background_tasks.add_task(skill_package_manager.run_install, request_id)

    return templates.TemplateResponse(
        request=request,
        name="ui/partials/install_status.html",
        context={
            "request_id": request_id,
            "status": SkillInstallStatus.QUEUED.value,
            "error": None,
            "skill_id": None,
            "poll": True,
        },
    )


@router.get("/skill-packages/{request_id}/status", response_class=HTMLResponse)
async def ui_install_status(request: Request, request_id: str):
    record = skill_install_store.get_install(request_id)
    if not record:
        return templates.TemplateResponse(
            request=request,
            name="ui/partials/install_status.html",
            context={
                "request_id": request_id,
                "status": SkillInstallStatus.FAILED.value,
                "error": "Install request not found",
                "skill_id": None,
                "poll": False,
            },
        )

    status = record.get("status", SkillInstallStatus.FAILED.value)
    poll = status in {SkillInstallStatus.QUEUED.value, SkillInstallStatus.RUNNING.value}
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/install_status.html",
        context={
            "request_id": request_id,
            "status": status,
            "error": record.get("error"),
            "skill_id": record.get("skill_id"),
            "poll": poll,
        },
    )
