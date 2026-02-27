from fastapi import APIRouter, status  # type: ignore[import-not-found]
from fastapi.responses import HTMLResponse  # type: ignore[import-not-found]

from ..services.engine_auth_flow_manager import engine_auth_flow_manager


router = APIRouter(tags=["oauth-callback"])


@router.get("/auth/callback", response_class=HTMLResponse)
async def handle_openai_oauth_callback_alias(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
):
    if not state or not state.strip():
        return HTMLResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content="<html><body><h3>OAuth callback failed</h3><p>Missing state.</p></body></html>",
        )
    try:
        payload = engine_auth_flow_manager.complete_openai_callback(
            state=state,
            code=code,
            error=error,
        )
    except ValueError as exc:
        return HTMLResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=f"<html><body><h3>OAuth callback failed</h3><p>{str(exc)}</p></body></html>",
        )
    except Exception as exc:
        return HTMLResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=f"<html><body><h3>OAuth callback failed</h3><p>{str(exc)}</p></body></html>",
        )

    if str(payload.get("status")) == "succeeded":
        return HTMLResponse(
            status_code=status.HTTP_200_OK,
            content="<html><body><h3>OAuth authorization successful</h3><p>You can close this page and return to Skill Runner.</p></body></html>",
        )
    return HTMLResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=f"<html><body><h3>OAuth callback failed</h3><p>{str(payload.get('error') or 'unknown error')}</p></body></html>",
    )
