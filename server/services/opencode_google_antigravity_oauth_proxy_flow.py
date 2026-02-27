from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .opencode_auth_store import OpencodeAuthStore

_AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
_CLIENT_ID_ENV = "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID"
_CLIENT_SECRET_ENV = "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET"
_REDIRECT_URI = "http://localhost:51121/oauth-callback"
_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
)


class AntigravityOAuthProxyError(RuntimeError):
    pass


@dataclass
class OpencodeGoogleAntigravityOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    code_verifier: str
    project_id: str
    auth_method: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


@dataclass
class _GoogleTokenPayload:
    access_token: str
    refresh_token: str
    expires_in: int
    email: str | None


def _utc_now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def _encode_state(verifier: str, project_id: str) -> str:
    payload = {
        "verifier": verifier,
        "projectId": project_id,
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_state(state: str) -> Dict[str, Any]:
    normalized = state.strip()
    if not normalized:
        raise AntigravityOAuthProxyError("OAuth state is required")
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise AntigravityOAuthProxyError("Invalid OAuth state payload") from exc
    if not isinstance(payload, dict):
        raise AntigravityOAuthProxyError("Invalid OAuth state payload")
    verifier = str(payload.get("verifier", "")).strip()
    if not verifier:
        raise AntigravityOAuthProxyError("OAuth state missing verifier")
    project_id = str(payload.get("projectId", "")).strip()
    return {
        "verifier": verifier,
        "projectId": project_id,
    }


def _parse_input_value(value: str) -> tuple[str, str | None]:
    normalized = value.strip()
    if not normalized:
        raise AntigravityOAuthProxyError("Input value is required")

    try:
        parsed = urllib_parse.urlparse(normalized)
    except Exception:
        return normalized, None

    if parsed.scheme and parsed.netloc:
        query = urllib_parse.parse_qs(parsed.query)
        code = str((query.get("code") or [""])[0]).strip()
        state = str((query.get("state") or [""])[0]).strip()
        if code:
            return code, state or None
    if "code=" in normalized:
        query = urllib_parse.parse_qs(normalized.split("?", 1)[-1])
        code = str((query.get("code") or [""])[0]).strip()
        state = str((query.get("state") or [""])[0]).strip()
        if code:
            return code, state or None
    return normalized, None


class OpencodeGoogleAntigravityOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.auth_store = OpencodeAuthStore(agent_home)

    def start_session(
        self,
        *,
        session_id: str,
        auth_method: str = "callback",
        now: datetime,
    ) -> OpencodeGoogleAntigravityOAuthProxySession:
        client_id, _ = self._google_oauth_credentials()
        verifier, challenge = _generate_pkce_pair()
        project_id = ""
        state = _encode_state(verifier, project_id)
        query = urllib_parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": _REDIRECT_URI,
                "scope": " ".join(_SCOPES),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
                "access_type": "offline",
                "prompt": "consent",
            }
        )
        auth_url = f"{_AUTHORIZE_ENDPOINT}?{query}"
        return OpencodeGoogleAntigravityOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=_REDIRECT_URI,
            code_verifier=verifier,
            project_id=project_id,
            auth_method=auth_method,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: OpencodeGoogleAntigravityOAuthProxySession, value: str) -> Dict[str, Any]:
        code, submitted_state = _parse_input_value(value)
        if submitted_state and submitted_state != runtime.state:
            raise AntigravityOAuthProxyError("OAuth state mismatch for this session")
        return self.complete_with_code(
            runtime=runtime,
            code=code,
            state=submitted_state or runtime.state,
        )

    def complete_with_code(
        self,
        *,
        runtime: OpencodeGoogleAntigravityOAuthProxySession,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        normalized_code = code.strip()
        normalized_state = state.strip()
        if not normalized_code:
            raise AntigravityOAuthProxyError("OAuth code is required")
        if normalized_state != runtime.state:
            raise AntigravityOAuthProxyError("OAuth state mismatch for this session")

        token_payload = self._exchange_code(
            code=normalized_code,
            verifier=runtime.code_verifier,
            project_id=runtime.project_id,
        )
        expires_at_ms = _utc_now_epoch_ms() + max(int(token_payload.expires_in), 1) * 1000
        stored_refresh = f"{token_payload.refresh_token}|{runtime.project_id or ''}"
        self.auth_store.upsert_oauth(
            provider_id="google",
            refresh_token=stored_refresh,
            access_token=token_payload.access_token,
            expires_at_ms=expires_at_ms,
            account_id=token_payload.email or None,
        )
        single_account_result = self.auth_store.overwrite_antigravity_single_account(
            refresh_token=stored_refresh,
            email=token_payload.email,
            project_id=runtime.project_id,
        )
        runtime.updated_at = datetime.now(timezone.utc)
        return {
            "google_antigravity_single_account_written": True,
            "google_antigravity_single_account_result": single_account_result,
            "callback_mode": "manual" if runtime.auth_method == "auth_code_or_url" else "auto",
        }

    def _exchange_code(self, *, code: str, verifier: str, project_id: str) -> _GoogleTokenPayload:
        client_id, client_secret = self._google_oauth_credentials()
        token_response = self._post_form(
            _TOKEN_ENDPOINT,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        access_token = str(token_response.get("access_token", "")).strip()
        refresh_token = str(token_response.get("refresh_token", "")).strip()
        expires_in_raw = token_response.get("expires_in")
        expires_in = 3600
        if isinstance(expires_in_raw, (int, float, str)):
            try:
                expires_in = int(expires_in_raw)
            except Exception:
                expires_in = 3600
        if not access_token or not refresh_token:
            raise AntigravityOAuthProxyError("Google token response missing required fields")

        email = self._fetch_email(access_token)
        return _GoogleTokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=max(expires_in, 1),
            email=email,
        )

    def _google_oauth_credentials(self) -> tuple[str, str]:
        client_id = str(os.environ.get(_CLIENT_ID_ENV, "")).strip()
        client_secret = str(os.environ.get(_CLIENT_SECRET_ENV, "")).strip()
        if not client_id:
            raise AntigravityOAuthProxyError(
                f"Missing Google OAuth client_id: set environment variable {_CLIENT_ID_ENV}"
            )
        if not client_secret:
            raise AntigravityOAuthProxyError(
                f"Missing Google OAuth client_secret: set environment variable {_CLIENT_SECRET_ENV}"
            )
        return client_id, client_secret

    def _post_form(self, url: str, payload: Dict[str, str]) -> Dict[str, Any]:
        body = urllib_parse.urlencode(payload).encode("utf-8")
        request = urllib_request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Accept": "*/*",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=25) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise AntigravityOAuthProxyError(
                f"Google token endpoint returned status {exc.code}: {detail[:300]}"
            ) from exc
        except urllib_error.URLError as exc:
            raise AntigravityOAuthProxyError(
                f"Google token endpoint request failed: {exc.reason}"
            ) from exc
        except Exception as exc:
            raise AntigravityOAuthProxyError(f"Google token endpoint request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise AntigravityOAuthProxyError("Google token endpoint returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise AntigravityOAuthProxyError("Google token endpoint returned invalid payload")
        return parsed

    def _fetch_email(self, access_token: str) -> str | None:
        request = urllib_request.Request(
            url=_USERINFO_ENDPOINT,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except Exception:
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        email = parsed.get("email")
        if isinstance(email, str) and email.strip():
            return email.strip()
        return None
