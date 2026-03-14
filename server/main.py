from contextlib import asynccontextmanager
import asyncio
import logging
import os
import signal
from pathlib import Path
from .config import config


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if value and ((value[0] == value[-1]) and value[0] in {"'", '"'}):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _load_shared_engine_auth_env_files() -> None:
    root = Path(__file__).resolve().parent.parent
    env_paths = (
        root / "server" / "engines" / "gemini" / "auth" / "protocol" / "shared_oauth_credentials.env",
        root / "server" / "engines" / "opencode" / "auth" / "protocol" / "shared_google_antigravity_oauth_credentials.env",
    )
    for env_path in env_paths:
        _load_env_file(env_path)


_load_shared_engine_auth_env_files()

from fastapi import FastAPI, APIRouter, HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import JSONResponse  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
from .logging_config import setup_logging
from .routers import skills, jobs, engines, management, local_runtime, oauth_callback, skill_packages, ui
from .services.engine_management.runtime_profile import get_runtime_profile
from .i18n import SUPPORTED_LANGUAGES, get_language, get_translator

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    from .services.engine_management.agent_cli_manager import AgentCliManager
    from .services.engine_management.engine_status_cache_service import engine_status_cache_service
    from .services.platform.cache_manager import cache_manager
    from .services.platform.concurrency_manager import concurrency_manager
    from .services.orchestration.run_cleanup_manager import run_cleanup_manager
    from .services.orchestration.runtime_observability_ports import install_runtime_observability_ports
    from .services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
    from .services.platform.process_supervisor import process_supervisor
    from .services.ui.ui_auth import validate_ui_basic_auth_config
    from .services.orchestration.job_orchestrator import job_orchestrator
    from .services.engine_management.engine_model_catalog_lifecycle import (
        engine_model_catalog_lifecycle,
    )
    from .runtime.auth_detection.service import auth_detection_service
    from .services.platform.local_runtime_lease_service import local_runtime_lease_service

    runtime_profile = get_runtime_profile()
    runtime_profile.ensure_directories()
    tmp_uploads_dir = getattr(config.SYSTEM, "TMP_UPLOADS_DIR", None)
    if not isinstance(tmp_uploads_dir, str) or not tmp_uploads_dir:
        data_dir = getattr(config.SYSTEM, "DATA_DIR", "data")
        tmp_uploads_dir = str(Path(data_dir) / "tmp_uploads")
    Path(tmp_uploads_dir).mkdir(parents=True, exist_ok=True)
    auth_detection_service.preload()
    cli_manager = AgentCliManager(runtime_profile)
    cli_manager.ensure_layout()
    try:
        await engine_status_cache_service.refresh_all()
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.warning(
            "Engine version cache refresh failed during startup; continuing with existing cache",
            extra={
                "component": "main",
                "action": "startup_engine_status_refresh",
                "error_type": type(exc).__name__,
                "fallback": "keep_existing_engine_status_cache",
            },
            exc_info=True,
        )
    engine_model_catalog_lifecycle.start()
    if bool(config.SYSTEM.ENGINE_MODELS_CATALOG_STARTUP_PROBE):
        for engine in engine_model_catalog_lifecycle.runtime_probe_engines():
            try:
                task = engine_model_catalog_lifecycle.request_refresh_async(engine, reason="startup")
                if task is None:
                    logger.warning(
                        "Engine model catalog refresh scheduling skipped during startup",
                        extra={
                            "component": "main",
                            "action": "startup_engine_model_catalog_refresh_schedule",
                            "engine": engine,
                            "fallback": "keep_existing_engine_model_catalog_cache",
                        },
                    )
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                logger.warning(
                    "Engine model catalog refresh scheduling failed during startup; continuing with existing cache",
                    extra={
                        "component": "main",
                        "action": "startup_engine_model_catalog_refresh_schedule",
                        "engine": engine,
                        "error_type": type(exc).__name__,
                        "fallback": "keep_existing_engine_model_catalog_cache",
                    },
                    exc_info=True,
                )
    install_runtime_protocol_ports()
    install_runtime_observability_ports()

    validate_ui_basic_auth_config()
    process_supervisor.start()
    try:
        await process_supervisor.reap_orphan_leases_on_startup()
    except (OSError, RuntimeError, ValueError):
        logger.warning("Startup orphan process reap failed", exc_info=True)
    concurrency_manager.start()
    cache_manager.start()
    engine_status_cache_service.start()
    run_cleanup_manager.start()
    runtime_profile_mode = str(getattr(runtime_profile, "mode", "local")).strip().lower() or "local"

    async def _shutdown_for_local_lease(reason: str) -> None:
        if runtime_profile_mode != "local":
            return
        if os.environ.get("PYTEST_CURRENT_TEST"):
            logger.info("Skip local runtime self-shutdown under pytest: reason=%s", reason)
            return
        logger.info("Local runtime lease shutdown requested: reason=%s", reason)
        async def _delayed_shutdown() -> None:
            try:
                await asyncio.sleep(0.5)
                os.kill(os.getpid(), signal.SIGTERM)
            except (OSError, ValueError):
                logger.warning("Failed to trigger local runtime shutdown", exc_info=True)

        asyncio.create_task(_delayed_shutdown())

    await local_runtime_lease_service.start(_shutdown_for_local_lease)
    await job_orchestrator.recover_incomplete_runs_on_startup()
    try:
        yield
    finally:
        await local_runtime_lease_service.stop()
        await process_supervisor.stop()
        engine_status_cache_service.stop()
        engine_model_catalog_lifecycle.stop()

app = FastAPI(
    title="Agent Skill Runner",
    description="A lightweight REST service to run CLI agent skills.",
    version="0.2.0",
    lifespan=lifespan
)


@app.middleware("http")
async def i18n_middleware(request: Request, call_next):
    request.state.lang = get_language(request)
    request.state.t = get_translator(request)
    selected_lang = request.query_params.get("lang", "").strip().lower()
    response = await call_next(request)
    if selected_lang in SUPPORTED_LANGUAGES:
        response.set_cookie(
            key="lang",
            value=selected_lang,
            max_age=31536000,
            path="/",
            samesite="lax",
        )
    return response


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if not accept:
        return False
    return "text/html" in accept.lower()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/ui") and _prefers_html(request):
        message = str(exc.detail) if exc.detail is not None else "Request failed."
        return ui.templates.TemplateResponse(
            request=request,
            name="ui/error.html",
            status_code=exc.status_code,
            context={
                "status_code": exc.status_code,
                "message": message,
                "back_href": "/ui",
            },
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error", exc_info=exc)
    if request.url.path.startswith("/ui") and _prefers_html(request):
        return ui.templates.TemplateResponse(
            request=request,
            name="ui/error.html",
            status_code=500,
            context={
                "status_code": 500,
                "message": "Internal Server Error",
                "back_href": "/ui",
            },
        )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

runtime_profile = get_runtime_profile()

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(skills.router)
v1_router.include_router(jobs.router)
v1_router.include_router(engines.router)
v1_router.include_router(management.router)
v1_router.include_router(local_runtime.router)
v1_router.include_router(skill_packages.router)
app.include_router(v1_router)
app.include_router(ui.router)
app.include_router(oauth_callback.router)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "assets" / "static")), name="static")

@app.get("/")
async def root():
    return {"message": "Agent Skill Runner is running"}
