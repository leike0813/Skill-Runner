import logging
import os
import uuid
import inspect
from collections.abc import Mapping
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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # type: ignore[import-not-found]
from fastapi.templating import Jinja2Templates  # type: ignore[import-not-found]

from ..models import (
    AuthSessionInputRequestV2,
    AuthSessionStartRequestV2,
    EngineAuthSessionInputRequest,
    EngineAuthSessionStartRequest,
    EngineUpgradeTaskStatus,
    RunStatus,
    SkillInstallStatus,
)
from ..runtime.auth.orchestrators.cli_delegate import CliDelegateOrchestrator
from ..runtime.auth.orchestrators.oauth_proxy import OAuthProxyOrchestrator
from ..services.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeValidationError,
    engine_upgrade_manager,
)
from ..services.engine_auth_flow_manager import engine_auth_flow_manager
from ..services.engine_interaction_gate import EngineInteractionBusyError
from ..services.model_registry import model_registry
from ..engines.opencode.auth.provider_registry import opencode_auth_provider_registry
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
from ..services.ui_shell_manager import (
    UiShellBusyError,
    UiShellRuntimeError,
    UiShellValidationError,
    ui_shell_manager,
)
from . import management as management_router


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))


router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    dependencies=[Depends(require_ui_basic_auth)],
)
agent_cli_manager = AgentCliManager()
oauth_proxy_orchestrator = OAuthProxyOrchestrator(engine_auth_flow_manager)
cli_delegate_orchestrator = CliDelegateOrchestrator(engine_auth_flow_manager)
logger = logging.getLogger(__name__)

LEGACY_UI_DATA_API_MODE = os.environ.get("SKILL_RUNNER_UI_LEGACY_API_MODE", "warn").strip().lower()
LEGACY_UI_DATA_API_SUNSET = os.environ.get("SKILL_RUNNER_UI_LEGACY_API_SUNSET", "2026-06-30")
LEGACY_UI_DATA_API_REPLACEMENT_DOC = os.environ.get(
    "SKILL_RUNNER_UI_LEGACY_API_REPLACEMENT_DOC",
    "/docs/api_reference.md#management-api-recommended",
)


def _build_auth_ui_capabilities(
    opencode_provider_modes: dict[str, str],
) -> dict[str, object]:
    oauth_proxy_opencode: dict[str, list[str]] = {}
    cli_delegate_opencode: dict[str, list[str]] = {}
    capabilities: dict[str, object] = {
        "oauth_proxy": {
            "codex": ["callback", "auth_code_or_url"],
            "gemini": ["callback", "auth_code_or_url"],
            "iflow": ["callback", "auth_code_or_url"],
            "opencode": oauth_proxy_opencode,
        },
        "cli_delegate": {
            "codex": ["callback", "auth_code_or_url"],
            "gemini": ["auth_code_or_url"],
            "iflow": ["auth_code_or_url"],
            "opencode": cli_delegate_opencode,
        },
    }
    for provider_id, auth_mode in opencode_provider_modes.items():
        normalized_provider = str(provider_id).strip().lower()
        normalized_mode = str(auth_mode).strip().lower()
        if not normalized_provider:
            continue
        if normalized_provider == "openai":
            oauth_proxy_opencode[normalized_provider] = ["callback", "auth_code_or_url"]
            cli_delegate_opencode[normalized_provider] = ["callback", "auth_code_or_url"]
            continue
        if normalized_provider == "google":
            oauth_proxy_opencode[normalized_provider] = ["callback", "auth_code_or_url"]
            cli_delegate_opencode[normalized_provider] = ["auth_code_or_url"]
            continue
        if normalized_mode == "api_key":
            oauth_proxy_opencode[normalized_provider] = ["api_key"]
            continue
        if normalized_mode == "oauth":
            oauth_proxy_opencode[normalized_provider] = ["callback", "auth_code_or_url"]
            cli_delegate_opencode[normalized_provider] = ["auth_code_or_url"]
    return capabilities


def _legacy_data_headers(replacement_path: str) -> dict[str, str]:
    return {
        "Deprecation": "true",
        "Sunset": LEGACY_UI_DATA_API_SUNSET,
        "Link": f'<{replacement_path}>; rel="successor-version", <{LEGACY_UI_DATA_API_REPLACEMENT_DOC}>; rel="deprecation"',
    }


def _handle_legacy_data_endpoint(endpoint: str, replacement_path: str) -> None:
    logger.warning(
        "Deprecated UI data endpoint called: endpoint=%s replacement=%s mode=%s",
        endpoint,
        replacement_path,
        LEGACY_UI_DATA_API_MODE,
    )
    if LEGACY_UI_DATA_API_MODE == "gone":
        raise HTTPException(
            status_code=410,
            detail=f"Deprecated endpoint removed. Use '{replacement_path}'",
        )


async def _resolve_async(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _payload_get(payload: object, key: str, default=None):
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return getattr(payload, key, default)


def _serialize_payload_item(item: object) -> dict[str, object]:
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "__dict__"):
        return dict(vars(item))
    raise TypeError(f"Unsupported payload item type: {type(item)!r}")


def _serialize_payload_list(payload: object, key: str) -> list[dict[str, object]]:
    raw_items = _payload_get(payload, key, [])
    if raw_items is None:
        return []
    return [_serialize_payload_item(item) for item in raw_items]


def _render_skills_table(
    request: Request,
    skills: list,
    highlight_skill_id: str | None = None,
) -> HTMLResponse:
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
    skills_payload = await _resolve_async(management_router.list_management_skills())
    return templates.TemplateResponse(
        request=request,
        name="ui/index.html",
        context={"skills": _payload_get(skills_payload, "skills", [])},
    )


@router.get("/management/skills/table", response_class=HTMLResponse)
async def ui_management_skills_table(request: Request, highlight_skill_id: str | None = None):
    skills_payload = await _resolve_async(management_router.list_management_skills())
    return _render_skills_table(
        request=request,
        skills=list(_payload_get(skills_payload, "skills", [])),
        highlight_skill_id=highlight_skill_id,
    )


@router.get("/skills/table", response_class=HTMLResponse)
async def ui_skills_table(request: Request, highlight_skill_id: str | None = None):
    replacement = f"/ui/management/skills/table?highlight_skill_id={highlight_skill_id or ''}"
    _handle_legacy_data_endpoint("/ui/skills/table", replacement)
    response = await ui_management_skills_table(request, highlight_skill_id)
    response.headers.update(_legacy_data_headers("/ui/management/skills/table"))
    return response


@router.get("/skills/{skill_id}", response_class=HTMLResponse)
async def ui_skill_detail(request: Request, skill_id: str):
    detail = await _resolve_async(management_router.get_management_skill(skill_id))
    return templates.TemplateResponse(
        request=request,
        name="ui/skill_detail.html",
        context={
            "skill": detail,
            "entries": detail.files,
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


@router.get("/management/runs/table", response_class=HTMLResponse)
async def ui_management_runs_table(request: Request):
    runs_payload = await _resolve_async(management_router.list_management_runs(limit=200))
    runs = _serialize_payload_list(runs_payload, "runs")
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/runs_table.html",
        context={"runs": runs},
    )


@router.get("/runs/table", response_class=HTMLResponse)
async def ui_runs_table(request: Request):
    _handle_legacy_data_endpoint("/ui/runs/table", "/ui/management/runs/table")
    response = await ui_management_runs_table(request)
    response.headers.update(_legacy_data_headers("/ui/management/runs/table"))
    return response


@router.get("/runs/{request_id}", response_class=HTMLResponse)
async def ui_run_detail(request: Request, request_id: str):
    state = await _resolve_async(management_router.get_management_run(request_id))
    files = await _resolve_async(management_router.get_management_run_files(request_id))
    status = _payload_get(state, "status")
    updated_at = _payload_get(state, "updated_at")
    if hasattr(updated_at, "isoformat"):
        updated_at_value = updated_at.isoformat()
    elif updated_at is None:
        updated_at_value = ""
    else:
        updated_at_value = str(updated_at)
    detail = {
        "request_id": _payload_get(state, "request_id"),
        "run_id": _payload_get(state, "run_id"),
        "skill_id": _payload_get(state, "skill_id"),
        "engine": _payload_get(state, "engine"),
        "status": status.value if isinstance(status, RunStatus) else str(status),
        "updated_at": updated_at_value,
        "pending_interaction_id": _payload_get(state, "pending_interaction_id"),
        "interaction_count": _payload_get(state, "interaction_count"),
        "entries": _payload_get(files, "entries", []),
        "error": _payload_get(state, "error"),
    }

    return templates.TemplateResponse(
        request=request,
        name="ui/run_detail.html",
        context={"detail": detail},
    )


@router.get("/management/runs/{request_id}/view", response_class=HTMLResponse)
async def ui_management_run_view_file(request: Request, request_id: str, path: str):
    payload = await _resolve_async(management_router.get_management_run_file(request_id, path))
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/file_preview.html",
        context={
            "relative_path": _payload_get(payload, "path"),
            "preview": _payload_get(payload, "preview"),
        },
    )


@router.get("/runs/{request_id}/view", response_class=HTMLResponse)
async def ui_run_view_file(request: Request, request_id: str, path: str):
    _handle_legacy_data_endpoint(
        "/ui/runs/{request_id}/view",
        "/ui/management/runs/{request_id}/view",
    )
    response = await ui_management_run_view_file(request, request_id, path)
    response.headers.update(
        _legacy_data_headers(f"/ui/management/runs/{request_id}/view")
    )
    return response


@router.get("/runs/{request_id}/logs/tail", response_class=HTMLResponse)
async def ui_run_logs_tail(request: Request, request_id: str):
    _handle_legacy_data_endpoint(
        "/ui/runs/{request_id}/logs/tail",
        f"/v1/management/runs/{request_id}/events",
    )
    try:
        payload = run_observability_service.get_logs_tail(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    response = templates.TemplateResponse(
        request=request,
        name="ui/partials/run_logs_tail.html",
        context={"payload": payload},
    )
    response.headers.update(
        _legacy_data_headers(f"/v1/management/runs/{request_id}/events")
    )
    return response


@router.get("/engines", response_class=HTMLResponse)
async def ui_engines(request: Request):
    engines_payload = await _resolve_async(management_router.list_management_engines())
    opencode_providers = [
        {
            "provider_id": item.provider_id,
            "display_name": item.display_name,
            "auth_mode": item.auth_mode,
        }
        for item in opencode_auth_provider_registry.list()
    ]
    opencode_provider_modes = {
        str(item["provider_id"]).strip().lower(): str(item["auth_mode"]).strip().lower()
        for item in opencode_providers
    }
    return templates.TemplateResponse(
        request=request,
        name="ui/engines.html",
        context={
            "engines": _serialize_payload_list(engines_payload, "engines"),
            "session": ui_shell_manager.get_session_snapshot(),
            "auth_session": engine_auth_flow_manager.get_active_session_snapshot(),
            "opencode_auth_providers": opencode_providers,
            "auth_ui_capabilities": _build_auth_ui_capabilities(opencode_provider_modes),
            "ttyd_available": agent_cli_manager.resolve_ttyd_command() is not None,
        },
    )


@router.get("/engines/tui/session")
async def ui_engine_tui_session_status():
    return JSONResponse(ui_shell_manager.get_session_snapshot())


@router.post("/engines/auth/oauth-proxy/sessions")
async def ui_engine_auth_oauth_proxy_start(request: Request, body: AuthSessionStartRequestV2):
    if body.transport.strip().lower() != "oauth_proxy":
        raise HTTPException(status_code=422, detail="transport must be oauth_proxy")
    try:
        return JSONResponse(
            oauth_proxy_orchestrator.start_session(
                engine=body.engine,
                auth_method=body.auth_method,
                provider_id=body.provider_id,
                callback_base_url=str(request.base_url).rstrip("/"),
            )
        )
    except EngineInteractionBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/engines/auth/oauth-proxy/sessions/{session_id}")
async def ui_engine_auth_oauth_proxy_status(session_id: str):
    try:
        return JSONResponse(oauth_proxy_orchestrator.get_session(session_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/oauth-proxy/sessions/{session_id}/cancel")
async def ui_engine_auth_oauth_proxy_cancel(session_id: str):
    try:
        payload = oauth_proxy_orchestrator.cancel_session(session_id)
        return JSONResponse(
            {
                "session": payload,
                "canceled": str(payload.get("status")) == "canceled",
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/oauth-proxy/sessions/{session_id}/input")
async def ui_engine_auth_oauth_proxy_input(session_id: str, body: AuthSessionInputRequestV2):
    try:
        payload = oauth_proxy_orchestrator.input_session(session_id, body.kind, body.value)
        return JSONResponse(
            {
                "session": payload,
                "accepted": str(payload.get("status"))
                in {"code_submitted_waiting_result", "succeeded"},
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/cli-delegate/sessions")
async def ui_engine_auth_cli_delegate_start(request: Request, body: AuthSessionStartRequestV2):
    if body.transport.strip().lower() != "cli_delegate":
        raise HTTPException(status_code=422, detail="transport must be cli_delegate")
    try:
        return JSONResponse(
            cli_delegate_orchestrator.start_session(
                engine=body.engine,
                auth_method=body.auth_method,
                provider_id=body.provider_id,
                callback_base_url=str(request.base_url).rstrip("/"),
            )
        )
    except EngineInteractionBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/engines/auth/cli-delegate/sessions/{session_id}")
async def ui_engine_auth_cli_delegate_status(session_id: str):
    try:
        return JSONResponse(cli_delegate_orchestrator.get_session(session_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/cli-delegate/sessions/{session_id}/cancel")
async def ui_engine_auth_cli_delegate_cancel(session_id: str):
    try:
        payload = cli_delegate_orchestrator.cancel_session(session_id)
        return JSONResponse(
            {
                "session": payload,
                "canceled": str(payload.get("status")) == "canceled",
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/cli-delegate/sessions/{session_id}/input")
async def ui_engine_auth_cli_delegate_input(session_id: str, body: AuthSessionInputRequestV2):
    try:
        payload = cli_delegate_orchestrator.input_session(session_id, body.kind, body.value)
        return JSONResponse(
            {
                "session": payload,
                "accepted": str(payload.get("status"))
                in {"code_submitted_waiting_result", "succeeded"},
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/sessions")
async def ui_engine_auth_start(request: Request, body: EngineAuthSessionStartRequest):
    try:
        payload = engine_auth_flow_manager.start_session(
                engine=body.engine,
                method=body.method,
                auth_method=body.auth_method,
                provider_id=body.provider_id,
                transport=body.transport,
                callback_base_url=str(request.base_url).rstrip("/"),
            )
        payload["deprecated"] = True
        return JSONResponse(payload)
    except EngineInteractionBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/engines/auth/session/active")
async def ui_engine_auth_active_session():
    try:
        return JSONResponse(engine_auth_flow_manager.get_active_session_snapshot())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/engines/auth/sessions/{session_id}")
async def ui_engine_auth_status(session_id: str):
    try:
        payload = engine_auth_flow_manager.get_session(session_id)
        payload["deprecated"] = True
        return JSONResponse(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/sessions/{session_id}/cancel")
async def ui_engine_auth_cancel(session_id: str):
    try:
        payload = engine_auth_flow_manager.cancel_session(session_id)
        payload["deprecated"] = True
        return JSONResponse(
            {
                "session": payload,
                "canceled": str(payload.get("status")) == "canceled",
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/auth/sessions/{session_id}/input")
async def ui_engine_auth_input(session_id: str, body: EngineAuthSessionInputRequest):
    try:
        payload = engine_auth_flow_manager.input_session(session_id, body.kind, body.value)
        payload["deprecated"] = True
        return JSONResponse(
            {
                "session": payload,
                "accepted": str(payload.get("status"))
                in {"code_submitted_waiting_result", "succeeded"},
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/tui/session/start")
async def ui_engine_tui_start(engine: str = Form(...)):
    try:
        data = ui_shell_manager.start_session(engine)
        return JSONResponse(data)
    except UiShellBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except UiShellValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UiShellRuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/tui/session/input")
async def ui_engine_tui_input(text: str = Form(...)):
    raise HTTPException(status_code=410, detail="Direct input endpoint is removed; use ttyd gateway")


@router.post("/engines/tui/session/resize")
async def ui_engine_tui_resize(cols: int = Form(...), rows: int = Form(...)):
    raise HTTPException(status_code=410, detail="Resize endpoint is removed; use ttyd gateway")


@router.post("/engines/tui/session/stop")
async def ui_engine_tui_stop():
    return JSONResponse(ui_shell_manager.stop_session())


@router.get("/engines/table", response_class=HTMLResponse)
async def ui_engines_table(request: Request):
    _handle_legacy_data_endpoint("/ui/engines/table", "/ui/management/engines/table")
    response = await ui_management_engines_table(request)
    response.headers.update(_legacy_data_headers("/ui/management/engines/table"))
    return response


@router.get("/management/engines/table", response_class=HTMLResponse)
async def ui_management_engines_table(request: Request):
    engines_payload = await _resolve_async(management_router.list_management_engines())
    rows = _serialize_payload_list(engines_payload, "engines")
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
    snapshots_supported = engine != "opencode"
    return templates.TemplateResponse(
        request=request,
        name="ui/engine_models.html",
        context={
            "engine": engine,
            "view": view,
            "error": error,
            "message": message,
            "snapshots_supported": snapshots_supported,
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
    if engine == "opencode":
        return RedirectResponse(
            url=f"/ui/engines/{engine}/models?error=Engine+%27opencode%27+does+not+support+model+snapshots",
            status_code=303,
        )

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
