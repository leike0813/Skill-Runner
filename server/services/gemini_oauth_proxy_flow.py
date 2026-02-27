from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .oauth_openai_proxy_common import generate_pkce_pair, generate_state_token

_GEMINI_AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_GEMINI_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GEMINI_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
_GEMINI_CLIENT_ID_ENV = "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID"
_GEMINI_CLIENT_SECRET_ENV = "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET"
_GEMINI_SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
)


class GeminiOAuthProxyError(RuntimeError):
    pass


@dataclass
class GeminiOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    code_verifier: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


@dataclass
class _GeminiTokenPayload:
    access_token: str
    refresh_token: str | None
    token_type: str
    scope: str | None
    id_token: str | None
    expires_in: int | None


def _utc_now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class GeminiOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def oauth_creds_path(self) -> Path:
        return self.agent_home / ".gemini" / "oauth_creds.json"

    @property
    def google_accounts_path(self) -> Path:
        return self.agent_home / ".gemini" / "google_accounts.json"

    def start_session(
        self,
        *,
        session_id: str,
        callback_url: str,
        now: datetime,
    ) -> GeminiOAuthProxySession:
        client_id, _ = self._google_oauth_credentials()
        code_verifier, code_challenge = generate_pkce_pair()
        state = generate_state_token()
        query = urllib_parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": callback_url,
                "response_type": "code",
                "access_type": "offline",
                "scope": " ".join(_GEMINI_SCOPES),
                "code_challenge_method": "S256",
                "code_challenge": code_challenge,
                "state": state,
            }
        )
        auth_url = f"{_GEMINI_AUTHORIZE_ENDPOINT}?{query}"
        return GeminiOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=callback_url,
            code_verifier=code_verifier,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: GeminiOAuthProxySession, value: str) -> Dict[str, Any]:
        code, state = self._parse_input_value(value)
        if state and state != runtime.state:
            raise GeminiOAuthProxyError("OAuth state mismatch for this session")
        return self.complete_with_code(
            runtime=runtime,
            code=code,
            state=state or runtime.state,
        )

    def complete_with_code(
        self,
        *,
        runtime: GeminiOAuthProxySession,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        normalized_code = code.strip()
        normalized_state = state.strip()
        if not normalized_code:
            raise GeminiOAuthProxyError("OAuth code is required")
        if normalized_state != runtime.state:
            raise GeminiOAuthProxyError("OAuth state mismatch for this session")

        token_payload = self._exchange_code(
            code=normalized_code,
            code_verifier=runtime.code_verifier,
            redirect_uri=runtime.redirect_uri,
        )
        email = self._fetch_email(token_payload.access_token)
        self._write_oauth_creds(token_payload)
        self._upsert_google_accounts(email=email)
        runtime.updated_at = datetime.now(timezone.utc)
        return {"google_account_email": email}

    def _parse_input_value(self, value: str) -> tuple[str, str | None]:
        normalized = value.strip()
        if not normalized:
            raise GeminiOAuthProxyError("Input value is required")

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

    def _exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> _GeminiTokenPayload:
        client_id, client_secret = self._google_oauth_credentials()
        payload = self._post_form(
            _GEMINI_TOKEN_ENDPOINT,
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        access_token = str(payload.get("access_token", "")).strip()
        refresh_token_raw = payload.get("refresh_token")
        refresh_token = str(refresh_token_raw).strip() if isinstance(refresh_token_raw, str) else None
        token_type = str(payload.get("token_type") or "Bearer").strip() or "Bearer"
        scope_raw = payload.get("scope")
        scope = str(scope_raw).strip() if isinstance(scope_raw, str) and scope_raw.strip() else None
        id_token_raw = payload.get("id_token")
        id_token = str(id_token_raw).strip() if isinstance(id_token_raw, str) and id_token_raw.strip() else None
        expires_raw = payload.get("expires_in")
        expires_in: int | None
        try:
            expires_in = int(expires_raw) if expires_raw is not None else None
        except Exception:
            expires_in = None

        if not access_token:
            raise GeminiOAuthProxyError("Google token response missing access_token")
        return _GeminiTokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            scope=scope,
            id_token=id_token,
            expires_in=expires_in,
        )

    def _google_oauth_credentials(self) -> tuple[str, str]:
        client_id = str(os.environ.get(_GEMINI_CLIENT_ID_ENV, "")).strip()
        client_secret = str(os.environ.get(_GEMINI_CLIENT_SECRET_ENV, "")).strip()
        if not client_id:
            raise GeminiOAuthProxyError(
                f"Missing Google OAuth client_id: set environment variable {_GEMINI_CLIENT_ID_ENV}"
            )
        if not client_secret:
            raise GeminiOAuthProxyError(
                f"Missing Google OAuth client_secret: set environment variable {_GEMINI_CLIENT_SECRET_ENV}"
            )
        return client_id, client_secret

    def _post_form(self, url: str, data: Dict[str, str]) -> Dict[str, Any]:
        encoded = urllib_parse.urlencode(data).encode("utf-8")
        request = urllib_request.Request(
            url=url,
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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
            raise GeminiOAuthProxyError(
                f"Google token endpoint returned status {exc.code}: {detail[:300]}"
            ) from exc
        except urllib_error.URLError as exc:
            raise GeminiOAuthProxyError(f"Google token endpoint request failed: {exc.reason}") from exc
        except Exception as exc:
            raise GeminiOAuthProxyError(f"Google token endpoint request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise GeminiOAuthProxyError("Google token endpoint returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise GeminiOAuthProxyError("Google token endpoint returned invalid payload")
        return parsed

    def _fetch_email(self, access_token: str) -> str | None:
        request = urllib_request.Request(
            url=_GEMINI_USERINFO_ENDPOINT,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except Exception:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        email = payload.get("email")
        if isinstance(email, str) and email.strip():
            return email.strip()
        return None

    def _write_oauth_creds(self, token_payload: _GeminiTokenPayload) -> None:
        payload: Dict[str, Any] = {
            "access_token": token_payload.access_token,
            "token_type": token_payload.token_type,
        }
        if token_payload.refresh_token:
            payload["refresh_token"] = token_payload.refresh_token
        if token_payload.scope:
            payload["scope"] = token_payload.scope
        if token_payload.id_token:
            payload["id_token"] = token_payload.id_token
        if token_payload.expires_in is not None:
            payload["expiry_date"] = _utc_now_epoch_ms() + max(token_payload.expires_in, 1) * 1000

        self.oauth_creds_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.oauth_creds_path, payload, chmod_mode=0o600)

    def _upsert_google_accounts(self, *, email: str | None) -> None:
        active_email: str | None = None
        old_emails: list[str] = []
        try:
            existing = json.loads(self.google_accounts_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                existing_active = existing.get("active")
                existing_old = existing.get("old")
                if isinstance(existing_active, str) and existing_active.strip():
                    active_email = existing_active.strip()
                if isinstance(existing_old, list):
                    old_emails = [str(item) for item in existing_old if isinstance(item, str)]
        except Exception:
            pass

        normalized_email = (email or "").strip()
        if normalized_email:
            if active_email and active_email != normalized_email and active_email not in old_emails:
                old_emails.append(active_email)
            old_emails = [item for item in old_emails if item != normalized_email]
            active_email = normalized_email

        payload: Dict[str, Any] = {
            "active": active_email,
            "old": old_emails,
        }

        self.google_accounts_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.google_accounts_path, payload)

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any], *, chmod_mode: int | None = None) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        tmp_path = ""
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            os.replace(tmp_path, path)
            if chmod_mode is not None:
                try:
                    os.chmod(path, chmod_mode)
                except Exception:
                    pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
