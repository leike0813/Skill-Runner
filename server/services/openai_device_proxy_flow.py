from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .oauth_openai_proxy_common import (
    OPENAI_CLIENT_ID,
    OPENAI_ISSUER,
    OpenAITokenSet,
    exchange_authorization_code,
    poll_openai_device_authorization_code,
    request_openai_device_code,
)


@dataclass
class OpenAIDeviceProxySession:
    session_id: str
    issuer: str
    client_id: str
    redirect_uri: str
    device_auth_id: str
    user_code: str
    verification_url: str
    interval_seconds: int
    user_agent: str | None
    created_at: datetime
    updated_at: datetime
    last_poll_at: datetime | None = None
    next_poll_at: datetime | None = None
    completed: bool = False


class OpenAIDeviceProxyFlow:
    def start_session(
        self,
        *,
        session_id: str,
        now: datetime,
        issuer: str = OPENAI_ISSUER,
        client_id: str = OPENAI_CLIENT_ID,
        user_agent: str | None = None,
    ) -> OpenAIDeviceProxySession:
        started = request_openai_device_code(
            issuer=issuer,
            client_id=client_id,
            user_agent=user_agent,
        )
        interval_seconds = max(int(started.interval_seconds), 1)
        return OpenAIDeviceProxySession(
            session_id=session_id,
            issuer=issuer,
            client_id=client_id,
            redirect_uri=f"{issuer.rstrip('/')}/deviceauth/callback",
            device_auth_id=started.device_auth_id,
            user_code=started.user_code,
            verification_url=started.verification_url,
            interval_seconds=interval_seconds,
            user_agent=user_agent,
            created_at=now,
            updated_at=now,
            next_poll_at=now + timedelta(seconds=interval_seconds),
            completed=False,
        )

    def poll_once(self, runtime: OpenAIDeviceProxySession, *, now: datetime) -> OpenAITokenSet | None:
        runtime.updated_at = now
        if runtime.completed:
            return None
        if runtime.next_poll_at is not None and now < runtime.next_poll_at:
            return None

        runtime.last_poll_at = now
        runtime.next_poll_at = now + timedelta(seconds=max(runtime.interval_seconds, 1))
        polled = poll_openai_device_authorization_code(
            device_auth_id=runtime.device_auth_id,
            user_code=runtime.user_code,
            issuer=runtime.issuer,
            user_agent=runtime.user_agent,
        )
        if polled is None:
            return None

        tokens = exchange_authorization_code(
            code=polled.authorization_code,
            redirect_uri=runtime.redirect_uri,
            code_verifier=polled.code_verifier,
            issuer=runtime.issuer,
            client_id=runtime.client_id,
        )
        runtime.completed = True
        runtime.updated_at = now
        return tokens
