from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


OPENAI_ISSUER = "https://auth.openai.com"
OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_SCOPE = "openid profile email offline_access"


class OpenAIOAuthError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class OpenAITokenSet:
    id_token: str
    access_token: str
    refresh_token: str
    expires_in: int | None = None


@dataclass
class OpenAIDeviceCodeStart:
    device_auth_id: str
    user_code: str
    interval_seconds: int
    verification_url: str


@dataclass
class OpenAIDeviceAuthorizationCode:
    authorization_code: str
    code_verifier: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def generate_state_token() -> str:
    return secrets.token_urlsafe(32)


def build_openai_authorize_url(
    *,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    originator: str,
    issuer: str = OPENAI_ISSUER,
    client_id: str = OPENAI_CLIENT_ID,
) -> str:
    query = urllib_parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": OPENAI_SCOPE,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": state,
            "originator": originator,
        }
    )
    return f"{issuer}/oauth/authorize?{query}"


def extract_code_from_user_input(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise OpenAIOAuthError("Authorization code is required")

    try:
        parsed = urllib_parse.urlparse(normalized)
    except Exception:
        return normalized

    if parsed.scheme and parsed.netloc:
        query = urllib_parse.parse_qs(parsed.query)
        code_values = query.get("code")
        if code_values and code_values[0].strip():
            return code_values[0].strip()

    if "code=" in normalized:
        query_fragment = normalized.split("?", 1)[-1]
        query = urllib_parse.parse_qs(query_fragment)
        code_values = query.get("code")
        if code_values and code_values[0].strip():
            return code_values[0].strip()

    return normalized


def _post_form(
    *,
    url: str,
    form: Dict[str, str],
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    body = urllib_parse.urlencode(form).encode("utf-8")
    req = urllib_request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout_sec) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        message = f"OAuth endpoint returned status {exc.code}"
        if detail:
            message = f"{message}: {detail[:300]}"
        raise OpenAIOAuthError(message, status_code=exc.code) from exc
    except urllib_error.URLError as exc:
        raise OpenAIOAuthError(f"OAuth endpoint request failed: {exc.reason}") from exc
    except Exception as exc:
        raise OpenAIOAuthError(f"OAuth endpoint request failed: {exc}") from exc

    try:
        parsed = json.loads(payload)
    except Exception as exc:
        raise OpenAIOAuthError("OAuth endpoint returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise OpenAIOAuthError("OAuth endpoint returned invalid payload type")
    return parsed


def _post_json(
    *,
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str] | None = None,
    timeout_sec: int = 20,
) -> tuple[int, Dict[str, Any] | None, str]:
    body = json.dumps(payload).encode("utf-8")
    request_headers: Dict[str, str] = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib_request.Request(
        url=url,
        data=body,
        method="POST",
        headers=request_headers,
    )
    status_code = 0
    raw = ""
    try:
        with urllib_request.urlopen(req, timeout=timeout_sec) as resp:
            status_code = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        status_code = int(exc.code)
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
    except urllib_error.URLError as exc:
        raise OpenAIOAuthError(f"OAuth endpoint request failed: {exc.reason}") from exc
    except Exception as exc:
        raise OpenAIOAuthError(f"OAuth endpoint request failed: {exc}") from exc

    parsed: Dict[str, Any] | None = None
    if raw.strip():
        try:
            payload_obj = json.loads(raw)
            if isinstance(payload_obj, dict):
                parsed = payload_obj
        except Exception:
            parsed = None
    return status_code, parsed, raw


def request_openai_device_code(
    *,
    issuer: str = OPENAI_ISSUER,
    client_id: str = OPENAI_CLIENT_ID,
    user_agent: str | None = None,
) -> OpenAIDeviceCodeStart:
    url = f"{issuer.rstrip('/')}/api/accounts/deviceauth/usercode"
    headers = {"User-Agent": user_agent} if user_agent else None
    status, payload, raw = _post_json(
        url=url,
        payload={"client_id": client_id},
        headers=headers,
    )
    if status < 200 or status >= 300:
        detail = raw[:300] if raw else ""
        message = f"OpenAI device code request failed with status {status}"
        if detail:
            message = f"{message}: {detail}"
        raise OpenAIOAuthError(message, status_code=status)
    if not isinstance(payload, dict):
        raise OpenAIOAuthError("OpenAI device code response is invalid JSON")

    device_auth_id = str(payload.get("device_auth_id", "")).strip()
    user_code = str(payload.get("user_code") or payload.get("usercode") or "").strip()
    interval_raw = payload.get("interval")
    try:
        interval_seconds = int(str(interval_raw).strip()) if interval_raw is not None else 5
    except Exception:
        interval_seconds = 5
    interval_seconds = max(interval_seconds, 1)
    if not device_auth_id or not user_code:
        raise OpenAIOAuthError("OpenAI device code response missing required fields")

    return OpenAIDeviceCodeStart(
        device_auth_id=device_auth_id,
        user_code=user_code,
        interval_seconds=interval_seconds,
        verification_url=f"{issuer.rstrip('/')}/codex/device",
    )


def poll_openai_device_authorization_code(
    *,
    device_auth_id: str,
    user_code: str,
    issuer: str = OPENAI_ISSUER,
    user_agent: str | None = None,
) -> OpenAIDeviceAuthorizationCode | None:
    url = f"{issuer.rstrip('/')}/api/accounts/deviceauth/token"
    headers = {"User-Agent": user_agent} if user_agent else None
    status, payload, raw = _post_json(
        url=url,
        payload={
            "device_auth_id": device_auth_id,
            "user_code": user_code,
        },
        headers=headers,
    )

    if status == 200:
        if not isinstance(payload, dict):
            raise OpenAIOAuthError("OpenAI device token response is invalid JSON")
        authorization_code = str(payload.get("authorization_code", "")).strip()
        code_verifier = str(payload.get("code_verifier", "")).strip()
        if not authorization_code or not code_verifier:
            raise OpenAIOAuthError("OpenAI device token response missing required fields")
        return OpenAIDeviceAuthorizationCode(
            authorization_code=authorization_code,
            code_verifier=code_verifier,
        )

    if status in {403, 404}:
        return None

    detail = raw[:300] if raw else ""
    message = f"OpenAI device token polling failed with status {status}"
    if detail:
        message = f"{message}: {detail}"
    raise OpenAIOAuthError(message, status_code=status)


def exchange_authorization_code(
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    issuer: str = OPENAI_ISSUER,
    client_id: str = OPENAI_CLIENT_ID,
) -> OpenAITokenSet:
    payload = _post_form(
        url=f"{issuer}/oauth/token",
        form={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    id_token = str(payload.get("id_token", "")).strip()
    access_token = str(payload.get("access_token", "")).strip()
    refresh_token = str(payload.get("refresh_token", "")).strip()
    expires_raw = payload.get("expires_in")
    expires_in: int | None
    try:
        expires_in = int(expires_raw) if expires_raw is not None else None
    except Exception:
        expires_in = None
    if not id_token or not access_token or not refresh_token:
        raise OpenAIOAuthError("OAuth token exchange payload missing required tokens")
    return OpenAITokenSet(
        id_token=id_token,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def exchange_id_token_for_api_key(
    *,
    id_token: str,
    issuer: str = OPENAI_ISSUER,
    client_id: str = OPENAI_CLIENT_ID,
) -> str:
    payload = _post_form(
        url=f"{issuer}/oauth/token",
        form={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "client_id": client_id,
            "requested_token": "openai-api-key",
            "subject_token": id_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        },
    )
    api_key = str(payload.get("access_token", "")).strip()
    if not api_key:
        raise OpenAIOAuthError("OAuth API key exchange payload missing access_token")
    return api_key


def extract_account_id_from_id_token(id_token: str) -> Optional[str]:
    parts = id_token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
        claims = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(claims, dict):
        return None
    auth_claim = claims.get("https://api.openai.com/auth")
    if isinstance(auth_claim, dict):
        account_id = auth_claim.get("chatgpt_account_id")
        if isinstance(account_id, str) and account_id.strip():
            return account_id.strip()
    account_id = claims.get("chatgpt_account_id")
    if isinstance(account_id, str) and account_id.strip():
        return account_id.strip()
    orgs = claims.get("organizations")
    if isinstance(orgs, list) and orgs:
        first = orgs[0]
        if isinstance(first, dict):
            org_id = first.get("id")
            if isinstance(org_id, str) and org_id.strip():
                return org_id.strip()
    return None
