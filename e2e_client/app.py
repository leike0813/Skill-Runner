from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request  # type: ignore[import-not-found]
from fastapi.responses import JSONResponse  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]

from .config import load_settings
from .routes import router, templates
from server.i18n import SUPPORTED_LANGUAGES, get_language, get_translator


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(
        title="Skill Runner Built-in E2E Example Client",
        description="Independent UI client for E2E validation against management/jobs APIs.",
        version="0.1.0",
    )
    app.state.settings = settings
    app.include_router(router)

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

    static_dir = Path(__file__).parent.parent / "server" / "assets" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def _prefers_html(request: Request) -> bool:
        accept = request.headers.get("accept", "")
        return bool(accept and "text/html" in accept.lower())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if not request.url.path.startswith("/api") and _prefers_html(request):
            message = str(exc.detail) if exc.detail is not None else "Request failed."
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                status_code=exc.status_code,
                context={
                    "status_code": exc.status_code,
                    "message": message,
                    "back_href": "/",
                },
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _exc: Exception):
        if not request.url.path.startswith("/api") and _prefers_html(request):
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                status_code=500,
                context={
                    "status_code": 500,
                    "message": "Internal Server Error",
                    "back_href": "/",
                },
            )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

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
