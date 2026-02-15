import base64
import binascii
import secrets
import logging

from fastapi import HTTPException, WebSocket, status  # type: ignore[import-not-found]
from starlette.requests import HTTPConnection  # type: ignore[import-not-found]

from ..config import config


logger = logging.getLogger(__name__)


def is_ui_basic_auth_enabled() -> bool:
    return bool(config.SYSTEM.UI_BASIC_AUTH_ENABLED)


def get_ui_basic_auth_credentials() -> tuple[str, str]:
    return (
        str(config.SYSTEM.UI_BASIC_AUTH_USERNAME or ""),
        str(config.SYSTEM.UI_BASIC_AUTH_PASSWORD or ""),
    )


def validate_ui_basic_auth_config() -> None:
    enabled = is_ui_basic_auth_enabled()
    logger.info(
        "UI basic auth enabled: %s; protected routes: /ui/*, /v1/skill-packages/*",
        enabled,
    )
    if not enabled:
        return
    username, password = get_ui_basic_auth_credentials()
    if not username or not password:
        logger.error(
            "UI basic auth enabled but credentials are missing: "
            "UI_BASIC_AUTH_USERNAME/UI_BASIC_AUTH_PASSWORD"
        )
        raise RuntimeError(
            "UI basic auth is enabled but UI_BASIC_AUTH_USERNAME/UI_BASIC_AUTH_PASSWORD are missing"
        )


async def require_ui_basic_auth(
    connection: HTTPConnection,
) -> None:
    if not is_ui_basic_auth_enabled():
        return
    # WebSocket routes use dedicated websocket auth check; skip here to avoid
    # FastAPI dependency mismatch between HTTPBasic and websocket scope.
    if connection.scope.get("type") == "websocket":
        return

    authorization = connection.headers.get("authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    if not verify_ui_basic_auth_header(authorization):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _decode_basic_header(authorization: str) -> tuple[str, str] | None:
    if not authorization or not authorization.lower().startswith("basic "):
        return None
    token = authorization[6:].strip()
    if not token:
        return None
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def verify_ui_basic_auth_header(authorization: str | None) -> bool:
    if not is_ui_basic_auth_enabled():
        return True
    if not authorization:
        return False
    decoded = _decode_basic_header(authorization)
    if decoded is None:
        return False
    expected_user, expected_password = get_ui_basic_auth_credentials()
    username, password = decoded
    return secrets.compare_digest(username, expected_user) and secrets.compare_digest(
        password, expected_password
    )


async def require_ui_basic_auth_websocket(websocket: WebSocket) -> bool:
    if verify_ui_basic_auth_header(websocket.headers.get("authorization")):
        return True
    await websocket.close(code=1008)
    return False
