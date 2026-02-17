from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
from .logging_config import setup_logging
from .routers import skills, jobs, engines, management, skill_packages, temp_skill_runs, ui
from .services.runtime_profile import get_runtime_profile

@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    from .services.agent_cli_manager import AgentCliManager
    from .services.cache_manager import cache_manager
    from .services.concurrency_manager import concurrency_manager
    from .services.run_cleanup_manager import run_cleanup_manager
    from .services.temp_skill_cleanup_manager import temp_skill_cleanup_manager
    from .services.ui_auth import validate_ui_basic_auth_config
    from .services.job_orchestrator import job_orchestrator

    runtime_profile = get_runtime_profile()
    runtime_profile.ensure_directories()
    cli_manager = AgentCliManager(runtime_profile)
    cli_manager.ensure_layout()

    validate_ui_basic_auth_config()
    concurrency_manager.start()
    cache_manager.start()
    run_cleanup_manager.start()
    temp_skill_cleanup_manager.start()
    await job_orchestrator.recover_incomplete_runs_on_startup()
    yield

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

@app.get("/")
async def root():
    return {"message": "Agent Skill Runner is running"}
