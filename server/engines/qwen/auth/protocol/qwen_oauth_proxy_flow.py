from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_status(response: Any) -> str:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        if callable(getcode):
            try:
                status = getcode()
            except (AttributeError, OSError, TypeError, ValueError):  # pragma: no cover - defensive fallback
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
    except (AttributeError, OSError, TypeError, ValueError):  # pragma: no cover - defensive fallback
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
    poll_attempts: int = 0
    last_poll_result: str | None = None
    last_poll_error: str | None = None


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
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:  # pragma: no cover - platform/network boundary
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
        runtime.last_poll_result = "polling"
        runtime.last_poll_error = None
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
        runtime.poll_attempts += 1
        runtime.next_poll_at = current + timedelta(seconds=self.POLL_INTERVAL_SECONDS)
        runtime.last_poll_result = "polling"
        runtime.last_poll_error = None

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
            error_payload = self._parse_error_payload(error_raw)
            error_code = str(error_payload.get("error") or "").strip().lower()
            if exc.code == 400 and error_code == "authorization_pending":
                runtime.last_poll_result = "authorization_pending"
                return False
            if exc.code in {400, 429} and error_code == "slow_down":
                runtime.next_poll_at = current + timedelta(seconds=self.POLL_INTERVAL_SECONDS * 2)
                runtime.last_poll_result = "slow_down"
                return False
            if error_code in {"expired_token", "access_denied"}:
                detail = self._describe_error_payload(error_payload) or error_code
                runtime.last_poll_result = "failed"
                runtime.last_poll_error = detail
                raise RuntimeError(f"Authorization failed: {detail}") from exc
            if _is_waf_html(error_raw):
                preview = _body_preview(error_raw)
                runtime.last_poll_result = "failed"
                runtime.last_poll_error = preview
                raise RuntimeError(
                    f"Token request appears blocked by upstream WAF (status={exc.code}, body={preview})"
                ) from exc
            detail = _body_preview(error_raw)
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = detail
            raise RuntimeError(f"Token request failed: {exc.code} {exc.reason}. Response: {detail}") from exc
        except RuntimeError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:  # pragma: no cover - platform/network boundary
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = str(exc)
            raise RuntimeError(f"Token request failed: {exc}") from exc

        outcome = self._interpret_token_payload(payload, runtime=runtime, now=current)
        if not outcome:
            return False

        credentials = self._build_credentials(payload=payload, now=current)
        self._store_credentials(credentials)
        runtime.completed = True
        runtime.updated_at = current
        runtime.last_poll_result = "succeeded"
        runtime.last_poll_error = None
        logger.info("qwen oauth proxy token poll succeeded")
        return True

    def _parse_error_payload(self, raw: str) -> dict[str, Any]:
        if not raw.strip():
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:  # pragma: no cover - defensive fallback
            return {}
        return payload if isinstance(payload, dict) else {}

    def _describe_error_payload(self, payload: dict[str, Any]) -> str:
        code = str(payload.get("error") or "").strip()
        description = str(payload.get("error_description") or "").strip()
        if code and description:
            return f"{code} - {description}"
        return code or description

    def _interpret_token_payload(
        self,
        payload: dict[str, Any],
        *,
        runtime: QwenOAuthSession,
        now: datetime,
    ) -> bool:
        access_token = str(payload.get("access_token") or "").strip()
        if access_token:
            return True
        error_code = str(payload.get("error") or "").strip().lower()
        if error_code == "authorization_pending":
            runtime.last_poll_result = "authorization_pending"
            return False
        if error_code == "slow_down":
            runtime.next_poll_at = now + timedelta(seconds=self.POLL_INTERVAL_SECONDS * 2)
            runtime.last_poll_result = "slow_down"
            return False
        detail = self._describe_error_payload(payload)
        if detail:
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = detail
            raise RuntimeError(f"Authorization failed: {detail}")
        runtime.last_poll_result = "failed"
        runtime.last_poll_error = "missing_access_token"
        raise RuntimeError("Qwen token response missing access_token")

    def _build_credentials(
        self,
        *,
        payload: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        credentials: dict[str, Any] = {
            "access_token": str(payload.get("access_token") or "").strip(),
            "refresh_token": self._optional_string(payload.get("refresh_token")),
            "token_type": str(payload.get("token_type") or "Bearer").strip() or "Bearer",
        }
        resource_url = self._optional_string(payload.get("resource_url"))
        if resource_url is not None:
            credentials["resource_url"] = resource_url
        expires_in = self._positive_int_or_none(payload.get("expires_in"))
        if expires_in is not None:
            credentials["expiry_date"] = int(now.timestamp() * 1000) + expires_in * 1000
        return credentials

    def _optional_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    def _positive_int_or_none(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed if parsed > 0 else None

    def _store_credentials(self, credentials: dict[str, Any]) -> None:
        config_dir = self._qwen_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        path = self._credentials_path()
        path.write_text(
            json.dumps(credentials, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
