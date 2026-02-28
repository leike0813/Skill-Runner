from fastapi import APIRouter, status  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]

from ..runtime.auth.callbacks import oauth_callback_router
from ..services.orchestration.engine_auth_flow_manager import engine_auth_flow_manager


router = APIRouter(tags=["oauth-callback"])


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
        return oauth_callback_router.render_error(
            str(exc),
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return oauth_callback_router.render(payload)
