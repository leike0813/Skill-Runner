from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter  # type: ignore[import-not-found]
from .logging_config import setup_logging
from .routers import skills, jobs, engines, skill_packages, temp_skill_runs

@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    from .services.cache_manager import cache_manager
    from .services.concurrency_manager import concurrency_manager
    from .services.run_cleanup_manager import run_cleanup_manager
    from .services.temp_skill_cleanup_manager import temp_skill_cleanup_manager
    concurrency_manager.start()
    cache_manager.start()
    run_cleanup_manager.start()
    temp_skill_cleanup_manager.start()
    yield

app = FastAPI(
    title="Agent Skill Runner",
    description="A lightweight REST service to run CLI agent skills.",
    version="0.1.0",
    lifespan=lifespan
)

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(skills.router)
v1_router.include_router(jobs.router)
v1_router.include_router(engines.router)
v1_router.include_router(skill_packages.router)
v1_router.include_router(temp_skill_runs.router)
app.include_router(v1_router)

@app.get("/")
async def root():
    return {"message": "Agent Skill Runner is running"}
