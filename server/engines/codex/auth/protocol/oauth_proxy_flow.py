from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from server.engines.common.openai_auth.common import (
    OpenAITokenSet,
    OpenAIOAuthError,
    build_openai_authorize_url,
    exchange_authorization_code,
    exchange_id_token_for_api_key,
    extract_code_from_user_input,
    generate_pkce_pair,
    generate_state_token,
    utc_now_iso,
)


@dataclass
class CodexOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    code_verifier: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


class CodexOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def auth_path(self) -> Path:
        return self.agent_home / ".codex" / "auth.json"

    def start_session(
        self,
        *,
        session_id: str,
        callback_url: str,
        now: datetime,
    ) -> CodexOAuthProxySession:
        code_verifier, code_challenge = generate_pkce_pair()
        state = generate_state_token()
        auth_url = build_openai_authorize_url(
            redirect_uri=callback_url,
            state=state,
            code_challenge=code_challenge,
            originator="codex_cli_rs",
        )
        return CodexOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=callback_url,
            code_verifier=code_verifier,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: CodexOAuthProxySession, value: str) -> None:
        code = extract_code_from_user_input(value)
        self.complete_with_code(runtime, code)

    def complete_with_code(self, runtime: CodexOAuthProxySession, code: str) -> None:
        token_set = exchange_authorization_code(
            code=code,
            redirect_uri=runtime.redirect_uri,
            code_verifier=runtime.code_verifier,
        )
        self.complete_with_tokens(token_set)

    def complete_with_tokens(self, token_set: OpenAITokenSet) -> None:
        api_key: str | None = None
        try:
            api_key = exchange_id_token_for_api_key(id_token=token_set.id_token)
        except OpenAIOAuthError:
            api_key = None
        self._write_auth_file(
            id_token=token_set.id_token,
            access_token=token_set.access_token,
            refresh_token=token_set.refresh_token,
            api_key=api_key,
        )

    def _write_auth_file(
        self,
        *,
        id_token: str,
        access_token: str,
        refresh_token: str,
        api_key: str | None,
    ) -> None:
        payload = {
            "OPENAI_API_KEY": api_key,
            "tokens": {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_id": None,
            },
            "last_refresh": utc_now_iso(),
        }
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        tmp_path = ""
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(self.auth_path.parent)) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            os.replace(tmp_path, self.auth_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
