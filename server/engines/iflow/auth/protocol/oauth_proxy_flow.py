from __future__ import annotations

import base64
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

from server.engines.common.openai_auth.common import generate_state_token

_IFLOW_AUTHORIZE_ENDPOINT = "https://iflow.cn/oauth"
_IFLOW_TOKEN_ENDPOINT = "https://iflow.cn/oauth/token"
_IFLOW_USER_INFO_ENDPOINT = "https://iflow.cn/api/oauth/getUserInfo"
_IFLOW_CLIENT_ID = "10009311001"
_IFLOW_CLIENT_SECRET = "4Z3YjXycVsQvyGF1etiNlIBB4RsqSDtW"


class IFlowOAuthProxyError(RuntimeError):
    pass


@dataclass
class IFlowOAuthProxySession:
    session_id: str
    state: str
    redirect_uri: str
    auth_method: str
    auth_url: str
    created_at: datetime
    updated_at: datetime


@dataclass
class _IFlowTokenPayload:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str | None


def _utc_now_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class IFlowOAuthProxyFlow:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def iflow_dir(self) -> Path:
        return self.agent_home / ".iflow"

    @property
    def oauth_creds_path(self) -> Path:
        return self.iflow_dir / "oauth_creds.json"

    @property
    def iflow_accounts_path(self) -> Path:
        return self.iflow_dir / "iflow_accounts.json"

    @property
    def settings_path(self) -> Path:
        return self.iflow_dir / "settings.json"

    def start_session(
        self,
        *,
        session_id: str,
        callback_url: str,
        auth_method: str,
        now: datetime,
    ) -> IFlowOAuthProxySession:
        state = generate_state_token()
        query = urllib_parse.urlencode(
            {
                "client_id": _IFLOW_CLIENT_ID,
                "loginMethod": "phone",
                "type": "phone",
                "redirect": callback_url,
                "state": state,
            }
        )
        auth_url = f"{_IFLOW_AUTHORIZE_ENDPOINT}?{query}"
        return IFlowOAuthProxySession(
            session_id=session_id,
            state=state,
            redirect_uri=callback_url,
            auth_method=auth_method,
            auth_url=auth_url,
            created_at=now,
            updated_at=now,
        )

    def submit_input(self, runtime: IFlowOAuthProxySession, value: str) -> Dict[str, Any]:
        code, state = self._parse_input_value(value)
        if state and state != runtime.state:
            raise IFlowOAuthProxyError("OAuth state mismatch for this session")
        return self.complete_with_code(
            runtime=runtime,
            code=code,
            state=state or runtime.state,
        )

    def complete_with_code(
        self,
        *,
        runtime: IFlowOAuthProxySession,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        normalized_code = code.strip()
        normalized_state = state.strip()
        if not normalized_code:
            raise IFlowOAuthProxyError("OAuth code is required")
        if normalized_state and normalized_state != runtime.state:
            raise IFlowOAuthProxyError("OAuth state mismatch for this session")

        token_payload = self._exchange_code(
            code=normalized_code,
            redirect_uri=runtime.redirect_uri,
        )
        user_info = self._fetch_user_info(token_payload.access_token)
        self._write_iflow_oauth_files(token_payload=token_payload, user_info=user_info)
        runtime.updated_at = datetime.now(timezone.utc)
        return {
            "iflow_api_key_present": bool(str(user_info.get("apiKey", "")).strip()),
            "iflow_user_name": str(user_info.get("userName") or "").strip() or None,
        }

    def _parse_input_value(self, value: str) -> tuple[str, str | None]:
        normalized = value.strip()
        if not normalized:
            raise IFlowOAuthProxyError("Input value is required")

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
        redirect_uri: str,
    ) -> _IFlowTokenPayload:
        credentials = base64.b64encode(
            f"{_IFLOW_CLIENT_ID}:{_IFLOW_CLIENT_SECRET}".encode("utf-8")
        ).decode("utf-8")
        payload = self._post_form(
            _IFLOW_TOKEN_ENDPOINT,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": _IFLOW_CLIENT_ID,
                "client_secret": _IFLOW_CLIENT_SECRET,
            },
            headers={
                "Authorization": f"Basic {credentials}",
                "Accept": "application/json",
                "User-Agent": "iFlow-Cli",
            },
        )
        access_token = str(payload.get("access_token", "")).strip()
        refresh_token = str(payload.get("refresh_token", "")).strip()
        token_type = str(payload.get("token_type") or "Bearer").strip() or "Bearer"
        scope_raw = payload.get("scope")
        scope = str(scope_raw).strip() if isinstance(scope_raw, str) and scope_raw.strip() else None

        expires_in_raw = payload.get("expires_in")
        expires_in = 3600
        if isinstance(expires_in_raw, (int, float, str)):
            try:
                expires_in = int(expires_in_raw)
            except Exception:
                expires_in = 3600
        expires_in = max(expires_in, 1)

        if not access_token:
            raise IFlowOAuthProxyError("iFlow token response missing access_token")
        if not refresh_token:
            raise IFlowOAuthProxyError("iFlow token response missing refresh_token")

        return _IFlowTokenPayload(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            scope=scope,
        )

    def _fetch_user_info(self, access_token: str) -> Dict[str, Any]:
        request = urllib_request.Request(
            url=f"{_IFLOW_USER_INFO_ENDPOINT}?accessToken={urllib_parse.quote(access_token)}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "iFlow-Cli",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib_error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise IFlowOAuthProxyError(
                f"iFlow user info endpoint returned status {exc.code}: {detail[:300]}"
            ) from exc
        except urllib_error.URLError as exc:
            raise IFlowOAuthProxyError(f"iFlow user info request failed: {exc.reason}") from exc
        except Exception as exc:
            raise IFlowOAuthProxyError(f"iFlow user info request failed: {exc}") from exc

        try:
            payload = json.loads(raw)
        except Exception as exc:
            raise IFlowOAuthProxyError("iFlow user info endpoint returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise IFlowOAuthProxyError("iFlow user info endpoint returned invalid payload")

        success = payload.get("success")
        data = payload.get("data")
        if success is True and isinstance(data, dict):
            return data
        raise IFlowOAuthProxyError("Failed to fetch iFlow user info")

    def _post_form(
        self,
        url: str,
        data: Dict[str, str],
        *,
        headers: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        encoded = urllib_parse.urlencode(data).encode("utf-8")
        request_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if headers:
            request_headers.update(headers)
        request = urllib_request.Request(
            url=url,
            data=encoded,
            method="POST",
            headers=request_headers,
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
            raise IFlowOAuthProxyError(
                f"iFlow token endpoint returned status {exc.code}: {detail[:300]}"
            ) from exc
        except urllib_error.URLError as exc:
            raise IFlowOAuthProxyError(f"iFlow token endpoint request failed: {exc.reason}") from exc
        except Exception as exc:
            raise IFlowOAuthProxyError(f"iFlow token endpoint request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise IFlowOAuthProxyError("iFlow token endpoint returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise IFlowOAuthProxyError("iFlow token endpoint returned invalid payload")
        return parsed

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = ""
        with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        try:
            os.replace(temp_path, path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _write_json_atomic(self, path: Path, payload: Dict[str, Any]) -> None:
        self._write_text_atomic(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _write_iflow_oauth_files(
        self,
        *,
        token_payload: _IFlowTokenPayload,
        user_info: Dict[str, Any],
    ) -> None:
        self.iflow_dir.mkdir(parents=True, exist_ok=True)
        now_ms = _utc_now_epoch_ms()
        expiry_date = now_ms + token_payload.expires_in * 1000
        api_key = str(user_info.get("apiKey") or "").strip()

        oauth_creds_payload: Dict[str, Any] = {
            "access_token": token_payload.access_token,
            "refresh_token": token_payload.refresh_token,
            "expiry_date": int(expiry_date),
            "token_type": token_payload.token_type,
            "scope": token_payload.scope or "",
            "apiKey": api_key,
            "userId": str(user_info.get("userId") or "").strip(),
            "userName": str(user_info.get("userName") or "").strip(),
            "avatar": str(user_info.get("avatar") or "").strip(),
            "email": str(user_info.get("email") or "").strip(),
            "phone": str(user_info.get("phone") or "").strip(),
        }
        self._write_json_atomic(self.oauth_creds_path, oauth_creds_payload)

        iflow_accounts_payload: Dict[str, Any] = {
            "active": None,
            "old": [],
            "iflowApiKey": api_key,
        }
        self._write_json_atomic(self.iflow_accounts_path, iflow_accounts_payload)

        settings_payload = self._read_json(self.settings_path)
        settings_payload["selectedAuthType"] = "oauth-iflow"
        base_url = settings_payload.get("baseUrl")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            settings_payload["baseUrl"] = "https://apis.iflow.cn/v1"
        self._write_json_atomic(self.settings_path, settings_payload)
