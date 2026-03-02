import logging

from fastapi import APIRouter, status  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]

from ..runtime.auth.callbacks import oauth_callback_router
from ..services.engine_management.engine_auth_flow_manager import engine_auth_flow_manager


router = APIRouter(tags=["oauth-callback"])
logger = logging.getLogger(__name__)


@router.get("/auth/callback", response_class=HTMLResponse)
async def handle_openai_oauth_callback_alias(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
):
    try:
        callback_payload = oauth_callback_router.parse(
            state=state,
            code=code,
            error=error,
        )
        payload = oauth_callback_router.execute(
            callback_payload,
            lambda *, state, code=None, error=None: engine_auth_flow_manager.complete_callback(
                channel="openai",
                state=state,
                code=code,
                error=error,
            ),
        )
    except ValueError as exc:
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        # Router boundary mapping: preserve HTML error surface for callback failures.
        logger.exception(
            "oauth_callback.alias failed; returning HTTP 500",
            extra={
                "component": "router.oauth_callback",
                "action": "handle_openai_oauth_callback_alias",
                "error_type": type(exc).__name__,
                "fallback": "render_error_http_500",
            },
        )
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return oauth_callback_router.render(payload)
