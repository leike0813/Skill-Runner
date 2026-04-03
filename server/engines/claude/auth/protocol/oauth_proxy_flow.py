from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import parse as urlparse
from urllib import request as urlrequest


_AUTHORIZE_URL = "https://platform.claude.com/oauth/authorize"
_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
_MANUAL_REDIRECT_URL = "https://platform.claude.com/oauth/code/callback"
_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_SCOPES = [
    "user:profile",
    "user:inference",
    "user:sessions:claude_code",
    "user:mcp_servers",
    "user:file_upload",
]


def _utc_now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _generate_state() -> str:
    return secrets.token_urlsafe(24)


def _extract_code(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("Authorization code is required")
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse.urlsplit(text)
        code = urlparse.parse_qs(parsed.query).get("code", [""])[-1].strip()
        if not code:
            raise ValueError("OAuth callback URL does not contain code")
        return code
    return text


@dataclass
class ClaudeOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    code_verifier: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


class ClaudeOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def credentials_path(self) -> Path:
        return self.agent_home / ".claude" / ".credentials.json"

    def start_session(
        self,
        *,
        session_id: str,
        callback_url: str,
        now: datetime,
    ) -> ClaudeOAuthProxySession:
        code_verifier, code_challenge = _generate_pkce_pair()
        state = _generate_state()
        auth_url = (
            f"{_AUTHORIZE_URL}?"
            + urlparse.urlencode(
                {
                    "response_type": "code",
                    "client_id": _CLIENT_ID,
                    "redirect_uri": callback_url,
                    "scope": " ".join(_SCOPES),
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                    "state": state,
                }
            )
        )
        return ClaudeOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=callback_url,
            code_verifier=code_verifier,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: ClaudeOAuthProxySession, value: str) -> dict[str, object]:
        code = _extract_code(value)
        return self.complete_with_code(runtime=runtime, code=code, state=runtime.state)

    def complete_with_code(
        self,
        *,
        runtime: ClaudeOAuthProxySession,
        code: str,
        state: str,
    ) -> dict[str, object]:
        if state.strip() != runtime.state:
            raise ValueError("OAuth callback state mismatch")
        payload = {
            "grant_type": "authorization_code",
            "code": code.strip(),
            "redirect_uri": runtime.redirect_uri or _MANUAL_REDIRECT_URL,
            "client_id": _CLIENT_ID,
            "code_verifier": runtime.code_verifier,
            "state": state.strip(),
        }
        req = urlrequest.Request(
            _TOKEN_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=30.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        tokens = json.loads(raw)
        if not isinstance(tokens, dict):
            raise ValueError("Claude OAuth token response must be a JSON object")
        self._write_credentials(tokens)
        return {
            "credential_path": str(self.credentials_path),
            "transport": "oauth_proxy",
        }

    def _write_credentials(self, tokens: dict[str, object]) -> None:
        payload = {
            "claudeAiOauth": {
                "accessToken": tokens.get("access_token"),
                "refreshToken": tokens.get("refresh_token"),
                "expiresAt": tokens.get("expires_at") or tokens.get("expires_in"),
                "scopes": tokens.get("scope") or _SCOPES,
                "tokenType": tokens.get("token_type") or "Bearer",
            },
            "updatedAt": _utc_now_iso(),
        }
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        temp_path = ""
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(self.credentials_path.parent)) as tmp:
            tmp.write(content)
            temp_path = tmp.name
        try:
            os.replace(temp_path, self.credentials_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
