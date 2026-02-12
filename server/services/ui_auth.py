import secrets
import logging

from fastapi import Depends, HTTPException, status  # type: ignore[import-not-found]
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # type: ignore[import-not-found]

from ..config import config


_security = HTTPBasic(auto_error=False)
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


def require_ui_basic_auth(
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> None:
    if not is_ui_basic_auth_enabled():
        return
    username, password = get_ui_basic_auth_credentials()
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    valid = secrets.compare_digest(credentials.username, username) and secrets.compare_digest(
        credentials.password, password
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
