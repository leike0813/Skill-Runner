from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from .config import config


def _load_local_env_file() -> None:
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env.engine_auth.local"
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


_load_local_env_file()

from fastapi import FastAPI, APIRouter  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
from .logging_config import setup_logging
from .routers import skills, jobs, engines, management, oauth_callback, skill_packages, ui
from .services.engine_management.runtime_profile import get_runtime_profile

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

    runtime_profile = get_runtime_profile()
    runtime_profile.ensure_directories()
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
        try:
            for engine in engine_model_catalog_lifecycle.runtime_probe_engines():
                await engine_model_catalog_lifecycle.refresh(engine, reason="startup")
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.warning(
                "Engine model catalog refresh failed during startup; continuing with existing cache",
                extra={
                    "component": "main",
                    "action": "startup_engine_model_catalog_refresh",
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
    await job_orchestrator.recover_incomplete_runs_on_startup()
    try:
        yield
    finally:
        await process_supervisor.stop()
        engine_status_cache_service.stop()
        engine_model_catalog_lifecycle.stop()

app = FastAPI(
    title="Agent Skill Runner",
    description="A lightweight REST service to run CLI agent skills.",
    version="0.2.0",
    lifespan=lifespan
)

runtime_profile = get_runtime_profile()

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(skills.router)
v1_router.include_router(jobs.router)
v1_router.include_router(engines.router)
v1_router.include_router(management.router)
v1_router.include_router(skill_packages.router)
app.include_router(v1_router)
app.include_router(ui.router)
app.include_router(oauth_callback.router)

@app.get("/")
async def root():
    return {"message": "Agent Skill Runner is running"}
