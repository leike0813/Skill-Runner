from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from server.engines.common.openai_auth.common import (
    OpenAITokenSet,
    build_openai_authorize_url,
    exchange_authorization_code,
    extract_account_id_from_id_token,
    extract_code_from_user_input,
    generate_pkce_pair,
    generate_state_token,
    utc_now_epoch_ms,
)
from server.engines.opencode.auth.auth_store import OpencodeAuthStore


@dataclass
class OpencodeOpenAIOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    code_verifier: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


class OpencodeOpenAIOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.auth_store = OpencodeAuthStore(agent_home)

    def start_session(
        self,
        *,
        session_id: str,
        callback_url: str,
        now: datetime,
    ) -> OpencodeOpenAIOAuthProxySession:
        code_verifier, code_challenge = generate_pkce_pair()
        state = generate_state_token()
        auth_url = build_openai_authorize_url(
            redirect_uri=callback_url,
            state=state,
            code_challenge=code_challenge,
            originator="opencode",
        )
        return OpencodeOpenAIOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=callback_url,
            code_verifier=code_verifier,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: OpencodeOpenAIOAuthProxySession, value: str) -> None:
        code = extract_code_from_user_input(value)
        self.complete_with_code(runtime, code)

    def complete_with_code(self, runtime: OpencodeOpenAIOAuthProxySession, code: str) -> None:
        token_set = exchange_authorization_code(
            code=code,
            redirect_uri=runtime.redirect_uri,
            code_verifier=runtime.code_verifier,
        )
        self.complete_with_tokens(token_set)

    def complete_with_tokens(self, token_set: OpenAITokenSet) -> None:
        account_id = extract_account_id_from_id_token(token_set.id_token)
        expires_at_ms = utc_now_epoch_ms() + max(token_set.expires_in or 3600, 1) * 1000
        self.auth_store.upsert_oauth(
            provider_id="openai",
            refresh_token=token_set.refresh_token,
            access_token=token_set.access_token,
            expires_at_ms=expires_at_ms,
            account_id=account_id,
        )
