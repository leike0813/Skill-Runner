from __future__ import annotations

import uvicorn
from fastapi import FastAPI  # type: ignore[import-not-found]

from .config import load_settings
from .routes import router


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="Skill Runner Built-in E2E Example Client",
        description="Independent UI client for E2E validation against management/jobs APIs.",
        version="0.1.0",
    )
    app.state.settings = settings
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "e2e_client.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
