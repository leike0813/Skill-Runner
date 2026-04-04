from __future__ import annotations

import json
import platform
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from server.engines.common.openai_auth.common import generate_pkce_pair


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_status(response: Any) -> str:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        if callable(getcode):
            try:
                status = getcode()
            except Exception:  # pragma: no cover - defensive fallback
                status = None
    return str(status) if status is not None else "unknown"


def _body_preview(raw: str, *, limit: int = 200) -> str:
    compact = " ".join(raw.split())
    if not compact:
        return "<empty>"
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _is_waf_html(raw: str) -> bool:
    lowered = raw.lower()
    return "aliyun_waf_" in lowered or "<!doctypehtml>" in lowered


def _qwen_user_agent() -> str:
    system = platform.system().lower() or "unknown"
    machine = platform.machine().lower() or "unknown"
    return f"QwenCode/unknown ({system}; {machine})"


def _request_headers(*, include_request_id: bool) -> dict[str, str]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": _qwen_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
    }
    if include_request_id:
        headers["x-request-id"] = uuid4().hex
    return headers


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - defensive fallback
        return ""


def _load_json_response(*, response: Any, operation: str) -> dict[str, Any]:
    status = _http_status(response)
    raw = response.read().decode("utf-8", errors="replace")
    if not raw.strip():
        raise RuntimeError(f"{operation} returned empty response body (status={status})")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = _body_preview(raw)
        if _is_waf_html(raw):
            raise RuntimeError(
                f"{operation} appears blocked by upstream WAF (status={status}, body={preview})"
            ) from exc
        raise RuntimeError(f"{operation} returned non-JSON response (status={status}, body={preview})") from exc
    if not isinstance(payload, dict):
        payload_type = type(payload).__name__
        raise RuntimeError(f"{operation} returned JSON {payload_type}, expected object")
    return payload


@dataclass
class QwenOAuthSession:
    session_id: str
    device_code: str
    user_code: str
    verification_uri_complete: str
    code_verifier: str
    expires_in: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    polling_started: bool = False
    completed: bool = False
    last_poll_at: datetime | None = None
    next_poll_at: datetime | None = None


class QwenOAuthProxyFlow:
    """
    Qwen OAuth device-code flow used by the shared oauth_proxy transport.
    """

    AUTHORIZE_ENDPOINT = "https://chat.qwen.ai/api/v1/oauth2/device/code"
    TOKEN_ENDPOINT = "https://chat.qwen.ai/api/v1/oauth2/token"
    CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
    SCOPE = "openid profile email model.completion"
    POLL_INTERVAL_SECONDS = 2

    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    def _qwen_config_dir(self) -> Path:
        return self.agent_home / ".qwen"

    def _credentials_path(self) -> Path:
        return self._qwen_config_dir() / "oauth_creds.json"

    def start_session(
        self,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> QwenOAuthSession:
        started_at = now or _utc_now()
        code_verifier, code_challenge = generate_pkce_pair()
        body = urllib.parse.urlencode(
            {
                "client_id": self.CLIENT_ID,
                "scope": self.SCOPE,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.AUTHORIZE_ENDPOINT,
            data=body,
            headers=_request_headers(include_request_id=True),
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = _load_json_response(
                    response=response,
                    operation="Qwen device code request",
                )
        except urllib.error.HTTPError as exc:
            detail = _body_preview(_read_http_error_body(exc))
            raise RuntimeError(
                f"Failed to request Qwen device code: {exc.code} {exc.reason}. Response: {detail}"
            ) from exc
        except RuntimeError as exc:
            raise RuntimeError(f"Failed to request Qwen device code: {exc}") from exc
        except Exception as exc:  # pragma: no cover - urllib error shape differs by platform
            raise RuntimeError(f"Failed to request Qwen device code: {exc}") from exc

        required_keys = {
            "device_code",
            "user_code",
            "verification_uri_complete",
            "expires_in",
        }
        if not required_keys.issubset(payload):
            raise RuntimeError("Invalid device code response from Qwen OAuth")

        expires_in = max(int(payload["expires_in"]), 1)
        return QwenOAuthSession(
            session_id=session_id,
            device_code=str(payload["device_code"]),
            user_code=str(payload["user_code"]),
            verification_uri_complete=str(payload["verification_uri_complete"]),
            code_verifier=code_verifier,
            expires_in=expires_in,
            created_at=started_at,
            updated_at=started_at,
            expires_at=started_at + timedelta(seconds=expires_in),
            polling_started=False,
            completed=False,
            next_poll_at=started_at + timedelta(seconds=self.POLL_INTERVAL_SECONDS),
        )

    def submit_input(
        self,
        runtime: QwenOAuthSession,
        _value: str,
        *,
        now: datetime | None = None,
    ) -> None:
        self.start_polling(runtime, now=now, poll_now=True)

    def start_polling(
        self,
        runtime: QwenOAuthSession,
        *,
        now: datetime | None = None,
        poll_now: bool = False,
    ) -> None:
        submitted_at = now or _utc_now()
        runtime.updated_at = submitted_at
        runtime.polling_started = True
        runtime.last_poll_at = None
        if poll_now or runtime.next_poll_at is None:
            runtime.next_poll_at = submitted_at

    def poll_once(self, runtime: QwenOAuthSession, *, now: datetime | None = None) -> bool:
        current = now or _utc_now()
        runtime.updated_at = current
        if runtime.completed or not runtime.polling_started:
            return runtime.completed
        if runtime.next_poll_at is not None and current < runtime.next_poll_at:
            return False
        if current > runtime.expires_at:
            raise RuntimeError("Authorization timeout")

        runtime.last_poll_at = current
        runtime.next_poll_at = current + timedelta(seconds=self.POLL_INTERVAL_SECONDS)

        body = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": self.CLIENT_ID,
                "device_code": runtime.device_code,
                "code_verifier": runtime.code_verifier,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.TOKEN_ENDPOINT,
            data=body,
            headers=_request_headers(include_request_id=True),
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = _load_json_response(
                    response=response,
                    operation="Qwen token request",
                )
        except urllib.error.HTTPError as exc:
            error_raw = _read_http_error_body(exc)
            if exc.code == 400:
                try:
                    error_payload = json.loads(error_raw) if error_raw.strip() else {}
                except Exception:  # pragma: no cover - defensive fallback
                    error_payload = {}
                error_code = str(error_payload.get("error") or "").strip().lower()
                if error_code == "authorization_pending":
                    return False
                if error_code == "slow_down":
                    runtime.next_poll_at = current + timedelta(seconds=self.POLL_INTERVAL_SECONDS * 2)
                    return False
                if error_code in {"expired_token", "access_denied"}:
                    raise RuntimeError(f"Authorization failed: {error_code}") from exc
            detail = _body_preview(error_raw)
            raise RuntimeError(f"Token request failed: {exc.code} {exc.reason}. Response: {detail}") from exc
        except RuntimeError:
            raise
        except Exception as exc:  # pragma: no cover - urllib error shape differs by platform
            raise RuntimeError(f"Token request failed: {exc}") from exc

        credentials = {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token"),
            "token_type": payload.get("token_type", "Bearer"),
            "expiry_date": int(current.timestamp() * 1000)
            + int(payload.get("expires_in", 0)) * 1000,
        }
        self._store_credentials(credentials)
        runtime.completed = True
        runtime.updated_at = current
        return True

    def _store_credentials(self, credentials: dict[str, Any]) -> None:
        config_dir = self._qwen_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        path = self._credentials_path()
        path.write_text(
            json.dumps(credentials, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
