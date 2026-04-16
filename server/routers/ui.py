import logging
import os
import uuid
import inspect
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote_plus
from jinja2 import pass_context

from fastapi import (  # type: ignore[import-not-found]
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # type: ignore[import-not-found]
from fastapi.templating import Jinja2Templates  # type: ignore[import-not-found]

from ..config import config
from ..config_registry import keys
from ..i18n import get_language, get_translator
from ..logging_config import get_logging_settings_payload
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
from ..services.engine_management.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeValidationError,
    engine_upgrade_manager,
)
from ..services.engine_management.engine_status_cache_service import (
    engine_status_cache_service,
)
from ..services.engine_management.engine_auth_flow_manager import (
    engine_auth_flow_manager,
)
from ..services.engine_management.engine_interaction_gate import (
    EngineInteractionBusyError,
)
from ..services.engine_management.engine_auth_strategy_service import (
    engine_auth_strategy_service,
)
from ..services.engine_management.engine_custom_provider_service import (
    engine_custom_provider_service,
)
from ..services.engine_management.model_registry import model_registry
from ..services.orchestration.runtime_observability_ports import (
    install_runtime_observability_ports,
)
from ..services.orchestration.runtime_protocol_ports import (
    install_runtime_protocol_ports,
)
from ..services.engine_management.engine_model_catalog_lifecycle import (
    engine_model_catalog_lifecycle,
)
from ..services.engine_management.agent_cli_manager import AgentCliManager
from ..services.engine_management.provider_aware_auth import (
    list_engine_auth_providers,
    provider_aware_engines,
)
from ..services.skill.skill_browser import (
    build_preview_payload,
    list_skill_entries,
    resolve_skill_file_path,
)
from ..runtime.observability.run_observability import run_observability_service
from ..services.skill.skill_install_store import skill_install_store
from ..services.skill.skill_package_manager import skill_package_manager
from ..services.skill.skill_registry import skill_registry
from ..services.ui.ui_auth import require_ui_basic_auth
from ..services.platform.data_reset_service import DATA_RESET_CONFIRMATION_TEXT
from ..services.ui.ui_shell_manager import (
    UiShellBusyError,
    UiShellRuntimeError,
    UiShellValidationError,
    ui_shell_manager,
)
from . import management as management_router


TEMPLATE_ROOT = Path(__file__).parent.parent / "assets" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_ROOT))


@pass_context
def _template_translate(context, key: str, default: str | None = None, **kwargs):
    request = context.get("request")
    if request is not None and hasattr(request.state, "t"):
        return request.state.t(key, default=default, **kwargs)
    # Fallback for tests or edge paths without middleware context.
    if request is not None:
        translator = get_translator(request)
        return translator(key, default=default, **kwargs)
    return default if default is not None else key


@pass_context
def _template_lang(context):
    request = context.get("request")
    if request is None:
        return "zh"
    return getattr(request.state, "lang", get_language(request))


templates.env.globals["t"] = _template_translate
templates.env.globals["lang"] = _template_lang


router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    dependencies=[Depends(require_ui_basic_auth)],
)
agent_cli_manager = AgentCliManager()
oauth_proxy_orchestrator = OAuthProxyOrchestrator(engine_auth_flow_manager)
cli_delegate_orchestrator = CliDelegateOrchestrator(engine_auth_flow_manager)
logger = logging.getLogger(__name__)

install_runtime_protocol_ports()
install_runtime_observability_ports()

LEGACY_UI_DATA_API_MODE = (
    os.environ.get("SKILL_RUNNER_UI_LEGACY_API_MODE", "warn").strip().lower()
)
LEGACY_UI_DATA_API_SUNSET = os.environ.get(
    "SKILL_RUNNER_UI_LEGACY_API_SUNSET", "2026-06-30"
)
LEGACY_UI_DATA_API_REPLACEMENT_DOC = os.environ.get(
    "SKILL_RUNNER_UI_LEGACY_API_REPLACEMENT_DOC",
    "/docs/api_reference.md#management-api-recommended",
)


def _get_engine_models_context(
    engine: str, *, error: str | None = None, message: str | None = None
) -> dict[str, object]:
    view = model_registry.get_manifest_view(engine)
    snapshots_supported = model_registry.supports_model_snapshots(engine)
    return {
        "engine": engine,
        "view": view,
        "error": error,
        "message": message,
        "snapshots_supported": snapshots_supported,
    }


def _render_engine_models_panel(
    request: Request,
    *,
    engine: str,
    error: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/engine_models_panel.html",
        context=_get_engine_models_context(engine, error=error, message=message),
    )


def _raise_ui_internal_server_error(*, action: str, exc: Exception) -> NoReturn:
    logger.exception(
        "ui router internal failure; returning HTTP 500",
        extra={
            "component": "router.ui",
            "action": action,
            "error_type": type(exc).__name__,
            "fallback": "http_500",
        },
    )
    raise HTTPException(status_code=500, detail=str(exc))


def _request_opencode_catalog_refresh_if_needed(
    snapshot: object, *, reason: str
) -> None:
    if not isinstance(snapshot, Mapping):
        return
    engine = str(snapshot.get("engine") or "").strip().lower()
    status = str(snapshot.get("status") or "").strip().lower()
    if engine != "opencode" or status != "succeeded":
        return
    engine_model_catalog_lifecycle.request_refresh_async(
        "opencode",
        reason=reason,
    )


def _is_ttyd_available() -> bool:
    return agent_cli_manager.resolve_ttyd_command() is not None


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


def _serialize_datetime_for_ui(raw: object) -> str:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc).isoformat()
        return raw.astimezone(timezone.utc).isoformat()
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return raw
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        return parsed.astimezone(timezone.utc).isoformat()
    return ""


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


async def _list_management_runs_payload(*, page: int, page_size: int):
    try:
        return await _resolve_async(
            management_router.list_management_runs(
                page=page,
                page_size=page_size,
                limit=None,
            )
        )
    except TypeError:
        # Backward-compat for tests/legacy call sites monkeypatching old signature.
        return await _resolve_async(
            management_router.list_management_runs(limit=page_size)
        )


def _render_skills_table(
    request: Request,
    skills: list,
    highlight_skill_id: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/skills_table.html",
        context={
            "skills": _normalize_ui_skills_rows(skills),
            "highlight_skill_id": highlight_skill_id,
        },
    )


def _coerce_non_empty_str(raw: object, fallback: str) -> str:
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            return value
    return fallback


def _normalize_string_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                values.append(text)
    return values


def _normalize_execution_modes(raw: object) -> list[str]:
    modes = _normalize_string_list(raw)
    if not modes:
        return ["auto"]
    return list(dict.fromkeys(modes))


def _coerce_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_health_indicator(raw: object) -> dict[str, str]:
    text = raw.strip() if isinstance(raw, str) else ""
    normalized = text.lower()
    yellow_states = {"unknown", "pending", "degraded", "warning"}
    red_states = {"error", "unhealthy", "failed", "offline"}
    if normalized == "healthy":
        return {"level": "healthy", "fallback": text or "healthy"}
    if normalized in yellow_states:
        return {"level": "warning", "fallback": text or normalized}
    if normalized in red_states:
        return {"level": "error", "fallback": text or normalized}
    if text:
        return {"level": "warning", "fallback": text}
    return {"level": "warning", "fallback": "unknown"}


def _normalize_ui_skills_rows(rows: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in rows:
        payload = _serialize_payload_item(item)
        skill_id = _coerce_non_empty_str(payload.get("id"), "")
        if not skill_id:
            continue
        display_name = _coerce_non_empty_str(payload.get("name"), skill_id)
        engines = _normalize_string_list(
            payload.get("effective_engines")
        ) or _normalize_string_list(payload.get("engines"))
        health = _normalize_health_indicator(payload.get("health"))
        normalized.append(
            {
                "id": skill_id,
                "display_name": display_name,
                "raw_name": skill_id,
                "version": _coerce_non_empty_str(payload.get("version"), "-"),
                "engines": engines,
                "execution_modes": _normalize_execution_modes(
                    payload.get("execution_modes")
                ),
                "is_builtin": _coerce_bool(payload.get("is_builtin")),
                "health_level": health["level"],
                "health_fallback": health["fallback"],
            }
        )
    return normalized


def _engine_status_level(*, present: bool, version: object) -> str:
    version_text = version.strip() if isinstance(version, str) else ""
    if not present:
        return "error"
    if version_text:
        return "healthy"
    return "warning"


def _load_engine_status_snapshot() -> dict[str, object]:
    try:
        return dict(engine_status_cache_service.get_snapshot())
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.warning(
            "ui index failed to read engine status cache; falling back to unavailable markers",
            extra={
                "component": "router.ui",
                "action": "ui_index_engine_status",
                "error_type": type(exc).__name__,
                "fallback": "all_unavailable",
            },
            exc_info=True,
        )
        return {}


def _home_engine_status_rows() -> list[dict[str, str]]:
    snapshot = _load_engine_status_snapshot()
    rows: list[dict[str, str]] = []
    for engine in keys.ENGINE_KEYS:
        status = snapshot.get(engine)
        present = bool(getattr(status, "present", False))
        version = getattr(status, "version", None)
        rows.append(
            {
                "engine": engine,
                "status_level": _engine_status_level(present=present, version=version),
                "version": version.strip() if isinstance(version, str) else "",
            }
        )
    return rows


def _with_engine_status_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    snapshot = _load_engine_status_snapshot()
    enriched: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        engine = str(item.get("engine") or "").strip().lower()
        status = snapshot.get(engine)
        present = bool(getattr(status, "present", False))
        version = getattr(status, "version", None)
        item["managed_present"] = present
        item["status_level"] = _engine_status_level(present=present, version=version)
        sandbox_status = agent_cli_manager.collect_sandbox_status(engine)
        item["sandbox_warning_code"] = sandbox_status.get("warning_code")
        item["sandbox_warning_message"] = sandbox_status.get("message")
        item["sandbox_missing_dependencies"] = list(
            sandbox_status.get("missing_dependencies") or []
        )
        enriched.append(item)
    return enriched


async def _management_engine_rows(request: Request) -> list[dict[str, object]]:
    engines_payload = await _resolve_async(management_router.list_management_engines())
    rows = _with_engine_status_rows(_serialize_payload_list(engines_payload, "engines"))
    engine_ui_metadata = _build_engine_ui_metadata(request)
    for row in rows:
        engine = str(row.get("engine") or "").strip().lower()
        metadata = engine_ui_metadata.get(engine, {})
        row["auth_entry_label"] = metadata.get(
            "auth_entry_label",
            request.state.t(
                "ui.engines.table.auth_engine",
                default="Auth ({engine})",
                engine=engine,
            ),
        )
    return rows


def _build_engine_ui_metadata(request: Request) -> dict[str, dict[str, str]]:
    t = getattr(
        request.state,
        "t",
        lambda key, default=None, **kwargs: default if default is not None else key,
    )
    label_defaults = {
        "codex": "Codex",
        "gemini": "Gemini",
        "opencode": "OpenCode",
        "claude": "Claude Code",
        "qwen": "Qwen",
    }
    input_defaults: dict[str, dict[str, str]] = {
        "gemini": {
            "default_input_kind": "code",
            "default_input_label": t(
                "ui.engines.input_label_gemini",
                default="Paste the authorization code below and submit.",
            ),
        },
        "claude": {
            "default_input_kind": "text",
            "default_input_label": t(
                "ui.engines.input_label_claude",
                default="Paste the authorization code or callback URL below and submit.",
            ),
        },
        "qwen": {
            "default_input_kind": "text",
            "default_input_label": t(
                "ui.engines.input_label_qwen",
                default="请在浏览器完成授权后输入 'done' 或直接提交",
            ),
        },
    }
    payload: dict[str, dict[str, str]] = {}
    for engine in keys.ENGINE_KEYS:
        label = t(
            f"ui.engines.engine_{engine}",
            default=label_defaults.get(engine, engine),
        )
        item = {
            "label": label,
            "auth_entry_label": t(
                f"ui.engines.table.auth_{engine}",
                default=t(
                    "ui.engines.table.auth_engine",
                    default="Auth ({engine})",
                    engine=label,
                ),
                engine=label,
            ),
        }
        item.update(input_defaults.get(engine, {}))
        payload[engine] = item
    return payload


def _render_engine_upgrade_status(
    request: Request,
    request_id: str,
    status: str,
    results: dict,
    error: str | None,
    poll: bool,
    engine_rows: list[dict[str, object]] | None = None,
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
            "engine_rows": engine_rows,
            "ttyd_available": _is_ttyd_available(),
        },
    )


@router.get("", response_class=HTMLResponse)
async def ui_index(request: Request):
    skills_payload = await _resolve_async(management_router.list_management_skills())
    return templates.TemplateResponse(
        request=request,
        name="ui/index.html",
        context={
            "skills": _payload_get(skills_payload, "skills", []),
            "engine_status_rows": _home_engine_status_rows(),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def ui_settings(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="ui/settings.html",
        context={
            "logging_settings": get_logging_settings_payload(),
            "reset_confirmation_text": DATA_RESET_CONFIRMATION_TEXT,
            "engine_auth_session_log_persistence_enabled": bool(
                config.SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED
            ),
        },
    )


@router.get("/management/skills/table", response_class=HTMLResponse)
async def ui_management_skills_table(
    request: Request, highlight_skill_id: str | None = None
):
    skills_payload = await _resolve_async(management_router.list_management_skills())
    return _render_skills_table(
        request=request,
        skills=list(_payload_get(skills_payload, "skills", [])),
        highlight_skill_id=highlight_skill_id,
    )


@router.get("/skills/table", response_class=HTMLResponse)
async def ui_skills_table(request: Request, highlight_skill_id: str | None = None):
    replacement = (
        f"/ui/management/skills/table?highlight_skill_id={highlight_skill_id or ''}"
    )
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


@router.get("/skills/{skill_id}/preview")
async def ui_skill_preview_file_json(skill_id: str, path: str):
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
    return JSONResponse(
        content={
            "skill_id": skill_id,
            "path": Path(path).as_posix(),
            "preview": preview,
        }
    )


@router.get("/runs", response_class=HTMLResponse)
async def ui_runs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    return templates.TemplateResponse(
        request=request,
        name="ui/runs.html",
        context={
            "page": max(1, int(page)),
            "page_size": max(1, int(page_size)),
        },
    )


@router.get("/management/runs/table", response_class=HTMLResponse)
async def ui_management_runs_table(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    runs_payload = await _list_management_runs_payload(page=page, page_size=page_size)
    runs = _serialize_payload_list(runs_payload, "runs")
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/runs_table.html",
        context={
            "runs": runs,
            "page": _payload_get(runs_payload, "page", page),
            "page_size": _payload_get(runs_payload, "page_size", page_size),
            "total": _payload_get(runs_payload, "total", len(runs)),
            "total_pages": _payload_get(runs_payload, "total_pages", 0),
        },
    )


@router.get("/runs/table", response_class=HTMLResponse)
async def ui_runs_table(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    _handle_legacy_data_endpoint("/ui/runs/table", "/ui/management/runs/table")
    response = await ui_management_runs_table(
        request=request,
        page=page,
        page_size=page_size,
    )
    response.headers.update(_legacy_data_headers("/ui/management/runs/table"))
    return response


@router.get("/runs/{request_id}", response_class=HTMLResponse)
async def ui_run_detail(
    request: Request,
    request_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    state = await _resolve_async(management_router.get_management_run(request_id))
    files = await _resolve_async(management_router.get_management_run_files(request_id))
    status = _payload_get(state, "status")
    updated_at = _payload_get(state, "updated_at")
    updated_at_value = _serialize_datetime_for_ui(updated_at)
    detail = {
        "request_id": _payload_get(state, "request_id"),
        "run_id": _payload_get(state, "run_id"),
        "skill_id": _payload_get(state, "skill_id"),
        "engine": _payload_get(state, "engine"),
        "model": _payload_get(state, "model"),
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
        context={
            "detail": detail,
            "return_page": max(1, int(page)),
            "return_page_size": max(1, int(page_size)),
        },
    )


@router.get("/management/runs/{request_id}/view", response_class=HTMLResponse)
async def ui_management_run_view_file(request: Request, request_id: str, path: str):
    payload = await _resolve_async(
        management_router.get_management_run_file(request_id, path)
    )
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
        payload = await run_observability_service.get_logs_tail(request_id)
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
    rows = await _management_engine_rows(request)
    engine_ui_metadata = _build_engine_ui_metadata(request)
    ui_shell_engines = {
        str(item.get("engine") or "").strip().lower()
        for item in ui_shell_manager.list_commands()
    }
    for row in rows:
        engine = str(row.get("engine") or "").strip().lower()
        metadata = engine_ui_metadata.get(engine, {})
        row["auth_entry_label"] = metadata.get(
            "auth_entry_label",
            request.state.t(
                "ui.engines.table.auth_engine",
                default="Auth ({engine})",
                engine=engine,
            ),
        )
    custom_provider_engines = [
        {
            "engine": engine,
            "label": engine_ui_metadata.get(engine, {}).get("label", engine),
            "provider_tui_supported": engine in ui_shell_engines and engine == "claude",
        }
        for engine in keys.ENGINE_KEYS
        if engine_custom_provider_service.supports(engine)
    ]
    engine_auth_providers = {
        engine: [
            {
                "provider_id": item.provider_id,
                "display_name": item.display_name,
                "auth_mode": item.auth_mode,
                "supports_import": item.supports_import,
            }
            for item in list_engine_auth_providers(engine)
        ]
        for engine in provider_aware_engines()
    }
    return templates.TemplateResponse(
        request=request,
        name="ui/engines.html",
        context={
            "engines": rows,
            "rows": rows,
            "session": ui_shell_manager.get_session_snapshot(),
            "auth_session": engine_auth_flow_manager.get_active_session_snapshot(),
            "engine_auth_providers": engine_auth_providers,
            "auth_ui_capabilities": engine_auth_strategy_service.list_ui_capabilities(),
            "auth_ui_high_risk_capabilities": (
                engine_auth_strategy_service.list_ui_high_risk_capabilities()
            ),
            "engine_ui_metadata": engine_ui_metadata,
            "custom_provider_engines": custom_provider_engines,
            "ttyd_available": _is_ttyd_available(),
        },
    )


@router.get("/engines/tui/session")
async def ui_engine_tui_session_status():
    return JSONResponse(ui_shell_manager.get_session_snapshot())


@router.post("/engines/auth/oauth-proxy/sessions")
async def ui_engine_auth_oauth_proxy_start(
    request: Request, body: AuthSessionStartRequestV2
):
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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_oauth_proxy_start", exc=exc
        )


@router.get("/engines/auth/oauth-proxy/sessions/{session_id}")
async def ui_engine_auth_oauth_proxy_status(session_id: str):
    try:
        payload = oauth_proxy_orchestrator.get_session(session_id)
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_status_poll",
        )
        return JSONResponse(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_oauth_proxy_status", exc=exc
        )


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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_oauth_proxy_cancel", exc=exc
        )


@router.post("/engines/auth/oauth-proxy/sessions/{session_id}/input")
async def ui_engine_auth_oauth_proxy_input(
    session_id: str, body: AuthSessionInputRequestV2
):
    try:
        payload = oauth_proxy_orchestrator.input_session(
            session_id, body.kind, body.value
        )
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_input_submit",
        )
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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_oauth_proxy_input", exc=exc
        )


@router.post("/engines/auth/cli-delegate/sessions")
async def ui_engine_auth_cli_delegate_start(
    request: Request, body: AuthSessionStartRequestV2
):
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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_cli_delegate_start", exc=exc
        )


@router.get("/engines/auth/cli-delegate/sessions/{session_id}")
async def ui_engine_auth_cli_delegate_status(session_id: str):
    try:
        payload = cli_delegate_orchestrator.get_session(session_id)
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_status_poll",
        )
        return JSONResponse(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_cli_delegate_status", exc=exc
        )


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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_cli_delegate_cancel", exc=exc
        )


@router.post("/engines/auth/cli-delegate/sessions/{session_id}/input")
async def ui_engine_auth_cli_delegate_input(
    session_id: str, body: AuthSessionInputRequestV2
):
    try:
        payload = cli_delegate_orchestrator.input_session(
            session_id, body.kind, body.value
        )
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_input_submit",
        )
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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(
            action="ui_engine_auth_cli_delegate_input", exc=exc
        )


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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(action="ui_engine_auth_start", exc=exc)


@router.get("/engines/auth/session/active")
async def ui_engine_auth_active_session():
    try:
        return JSONResponse(engine_auth_flow_manager.get_active_session_snapshot())
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(action="ui_engine_auth_active_session", exc=exc)


@router.get("/engines/auth/sessions/{session_id}")
async def ui_engine_auth_status(session_id: str):
    try:
        payload = engine_auth_flow_manager.get_session(session_id)
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_status_poll",
        )
        payload["deprecated"] = True
        return JSONResponse(payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Auth session not found")
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(action="ui_engine_auth_status", exc=exc)


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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(action="ui_engine_auth_cancel", exc=exc)


@router.post("/engines/auth/sessions/{session_id}/input")
async def ui_engine_auth_input(session_id: str, body: EngineAuthSessionInputRequest):
    try:
        payload = engine_auth_flow_manager.input_session(
            session_id, body.kind, body.value
        )
        _request_opencode_catalog_refresh_if_needed(
            payload,
            reason="auth_success_input_submit",
        )
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
    except (RuntimeError, OSError, TypeError, LookupError, ValueError) as exc:
        _raise_ui_internal_server_error(action="ui_engine_auth_input", exc=exc)


@router.post("/engines/tui/session/start")
async def ui_engine_tui_start(
    engine: str = Form(...),
    custom_model: str | None = Form(default=None),
):
    if not _is_ttyd_available():
        raise HTTPException(
            status_code=503, detail="ttyd not found. Inline TUI is unavailable."
        )
    try:
        data = ui_shell_manager.start_session(engine, custom_model=custom_model)
        return JSONResponse(data)
    except UiShellBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except UiShellValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UiShellRuntimeError as exc:
        if "ttyd not found" in str(exc).lower():
            raise HTTPException(status_code=503, detail=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/engines/tui/session/input")
async def ui_engine_tui_input(text: str = Form(...)):
    raise HTTPException(
        status_code=410, detail="Direct input endpoint is removed; use ttyd gateway"
    )


@router.post("/engines/tui/session/resize")
async def ui_engine_tui_resize(cols: int = Form(...), rows: int = Form(...)):
    raise HTTPException(
        status_code=410, detail="Resize endpoint is removed; use ttyd gateway"
    )


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
    return templates.TemplateResponse(
        request=request,
        name="ui/partials/engines_table.html",
        context={
            "rows": await _management_engine_rows(request),
            "ttyd_available": _is_ttyd_available(),
        },
    )


@router.post("/engines/upgrades", response_class=HTMLResponse)
async def ui_create_engine_upgrade(
    request: Request,
    mode: str = Form(...),
    engine: str | None = Form(None),
):
    try:
        request_id = await engine_upgrade_manager.create_task(mode, engine)
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
    record = await engine_upgrade_manager.get_task(request_id)
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
    poll = status in {
        EngineUpgradeTaskStatus.QUEUED.value,
        EngineUpgradeTaskStatus.RUNNING.value,
    }
    engine_rows = None if poll else await _management_engine_rows(request)
    return _render_engine_upgrade_status(
        request=request,
        request_id=request_id,
        status=status,
        results=results,
        error=None,
        poll=poll,
        engine_rows=engine_rows,
    )


@router.get("/engines/{engine}/models", response_class=HTMLResponse)
async def ui_engine_models(
    request: Request, engine: str, error: str | None = None, message: str | None = None
):
    try:
        context = _get_engine_models_context(engine, error=error, message=message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return templates.TemplateResponse(
        request=request,
        name="ui/engine_models.html",
        context=context,
    )


@router.post("/engines/{engine}/models/refresh", response_class=HTMLResponse)
async def ui_engine_models_refresh(request: Request, engine: str):
    try:
        if not model_registry.supports_runtime_catalog_refresh(engine):
            return _render_engine_models_panel(
                request,
                engine=engine,
                error=f"Engine '{engine}' does not support runtime catalog refresh",
            )
        await engine_model_catalog_lifecycle.refresh(engine, reason="ui_manual_refresh")
        return _render_engine_models_panel(
            request,
            engine=engine,
            message="Model list refreshed",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (OSError, RuntimeError, TypeError) as exc:
        return _render_engine_models_panel(
            request,
            engine=engine,
            error=str(exc),
        )


@router.post("/engines/{engine}/models/snapshots")
async def ui_engine_models_add_snapshot(
    request: Request,
    engine: str,
    id: list[str] = Form(...),
    model: list[str] | None = Form(None),
    deprecated: list[str] | None = Form(None),
    notes: list[str] | None = Form(None),
    supported_effort: list[str] | None = Form(None),
):
    if not model_registry.supports_model_snapshots(engine):
        return RedirectResponse(
            url=f"/ui/engines/{engine}/models?error=Engine+%27{quote_plus(engine)}%27+does+not+support+model+snapshots",
            status_code=303,
        )

    model = model or []
    deprecated = deprecated or []
    notes = notes or []
    supported_effort = supported_effort or []
    models = []
    for index, model_id in enumerate(id):
        model_id_clean = model_id.strip()
        if not model_id_clean:
            continue
        model_value = model[index].strip() if index < len(model) else ""
        notes_value = notes[index].strip() if index < len(notes) else ""
        deprecated_raw = (
            deprecated[index].strip().lower() if index < len(deprecated) else "false"
        )
        effort_raw = (
            supported_effort[index].strip() if index < len(supported_effort) else ""
        )
        efforts = (
            [item.strip() for item in effort_raw.split(",") if item.strip()]
            if effort_raw
            else None
        )
        models.append(
            {
                "id": model_id_clean,
                "display_name": model_value or None,
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
    await skill_package_manager.create_install_request(request_id, payload)
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
    record = await skill_install_store.get_install(request_id)
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
