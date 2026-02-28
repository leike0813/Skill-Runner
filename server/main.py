from contextlib import asynccontextmanager
import os
from pathlib import Path


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
from .routers import skills, jobs, engines, management, oauth_callback, skill_packages, temp_skill_runs, ui
from .services.orchestration.runtime_profile import get_runtime_profile

@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    from .services.orchestration.agent_cli_manager import AgentCliManager
    from .services.platform.cache_manager import cache_manager
    from .services.platform.concurrency_manager import concurrency_manager
    from .services.orchestration.run_cleanup_manager import run_cleanup_manager
    from .services.orchestration.runtime_observability_ports import install_runtime_observability_ports
    from .services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
    from .services.skill.temp_skill_cleanup_manager import temp_skill_cleanup_manager
    from .services.ui.ui_auth import validate_ui_basic_auth_config
    from .services.orchestration.job_orchestrator import job_orchestrator
    from .engines.opencode.models.catalog_service import opencode_model_catalog

    runtime_profile = get_runtime_profile()
    runtime_profile.ensure_directories()
    cli_manager = AgentCliManager(runtime_profile)
    cli_manager.ensure_layout()
    opencode_model_catalog.start()
    install_runtime_protocol_ports()
    install_runtime_observability_ports()

    validate_ui_basic_auth_config()
    concurrency_manager.start()
    cache_manager.start()
    run_cleanup_manager.start()
    temp_skill_cleanup_manager.start()
    await job_orchestrator.recover_incomplete_runs_on_startup()
    try:
        yield
    finally:
        opencode_model_catalog.stop()

app = FastAPI(
    title="Agent Skill Runner",
    description="A lightweight REST service to run CLI agent skills.",
    version="0.2.0",
    lifespan=lifespan
)

runtime_profile = get_runtime_profile()
ui_static_dir = runtime_profile.data_dir / "ui_static"
ui_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/ui-static", StaticFiles(directory=str(ui_static_dir)), name="ui-static")

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(skills.router)
v1_router.include_router(jobs.router)
v1_router.include_router(engines.router)
v1_router.include_router(management.router)
v1_router.include_router(skill_packages.router)
v1_router.include_router(temp_skill_runs.router)
app.include_router(v1_router)
app.include_router(ui.router)
app.include_router(oauth_callback.router)

@app.get("/")
async def root():
    return {"message": "Agent Skill Runner is running"}
