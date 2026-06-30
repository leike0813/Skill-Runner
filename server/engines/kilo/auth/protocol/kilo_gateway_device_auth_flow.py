from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


_TOKEN_LIKE_PATTERN = re.compile(
    r"(?i)(authorization|token|access|refresh|api[_-]?key|cookie)([\"'\s:=]+)([^\"'\s,;}]+)"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(text: str) -> str:
    return _TOKEN_LIKE_PATTERN.sub(r"\1\2<redacted>", text)


def _body_preview(raw: str, *, limit: int = 240) -> str:
    compact = " ".join(raw.split())
    if not compact:
        return "<empty>"
    if len(compact) > limit:
        compact = f"{compact[:limit]}..."
    return _redact(compact)


def _http_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        try:
            code = getcode()
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return code if isinstance(code, int) else None
    return None


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except (AttributeError, OSError, TypeError, ValueError):
        return ""


def _load_json_response(*, response: Any, operation: str) -> dict[str, Any]:
    status = _http_status(response)
    raw = response.read().decode("utf-8", errors="replace")
    if not raw.strip():
        raise RuntimeError(f"{operation} returned empty response body (status={status or 'unknown'})")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{operation} returned non-JSON response (status={status or 'unknown'}, body={_body_preview(raw)})"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{operation} returned JSON {type(payload).__name__}, expected object")
    return payload


@dataclass
class KiloGatewayDeviceAuthSession:
    session_id: str
    code: str
    user_code: str
    verification_url: str
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


class KiloGatewayDeviceAuthFlow:
    CODES_ENDPOINT = "https://api.kilo.ai/api/device-auth/codes"
    POLL_INTERVAL_SECONDS = 2
    TOKEN_TTL_DAYS = 365

    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    @property
    def auth_path(self) -> Path:
        return self.agent_home / ".local" / "share" / "kilo" / "auth.json"

    def start_session(
        self,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> KiloGatewayDeviceAuthSession:
        started_at = now or _utc_now()
        request = urllib.request.Request(
            self.CODES_ENDPOINT,
            data=b"",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "kilo/skill-runner",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = _load_json_response(
                    response=response,
                    operation="Kilo device code request",
                )
        except urllib.error.HTTPError as exc:
            detail = _body_preview(_read_http_error_body(exc))
            raise RuntimeError(
                f"Failed to request Kilo device code: {exc.code} {exc.reason}. Response: {detail}"
            ) from exc
        except RuntimeError as exc:
            raise RuntimeError(f"Failed to request Kilo device code: {exc}") from exc
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"Failed to request Kilo device code: {_redact(str(exc))}") from exc

        code = self._required_string(payload, "code")
        verification_url = self._required_string(payload, "verificationUrl")
        user_code = self._optional_string(payload.get("userCode")) or code
        expires_in = self._positive_int(payload.get("expiresIn"), default=600)
        return KiloGatewayDeviceAuthSession(
            session_id=session_id,
            code=code,
            user_code=user_code,
            verification_url=verification_url,
            expires_in=expires_in,
            created_at=started_at,
            updated_at=started_at,
            expires_at=started_at + timedelta(seconds=expires_in),
            next_poll_at=started_at + timedelta(seconds=self.POLL_INTERVAL_SECONDS),
        )

    def start_polling(
        self,
        runtime: KiloGatewayDeviceAuthSession,
        *,
        now: datetime | None = None,
        poll_now: bool = False,
    ) -> None:
        current = now or _utc_now()
        runtime.updated_at = current
        runtime.polling_started = True
        runtime.last_poll_at = None
        runtime.last_poll_result = "polling"
        runtime.last_poll_error = None
        if poll_now or runtime.next_poll_at is None:
            runtime.next_poll_at = current

    def poll_once(
        self,
        runtime: KiloGatewayDeviceAuthSession,
        *,
        now: datetime | None = None,
    ) -> bool:
        current = now or _utc_now()
        runtime.updated_at = current
        if runtime.completed or not runtime.polling_started:
            return runtime.completed
        if runtime.next_poll_at is not None and current < runtime.next_poll_at:
            return False
        if current > runtime.expires_at:
            runtime.last_poll_result = "expired"
            raise RuntimeError("Authorization timeout")

        runtime.last_poll_at = current
        runtime.poll_attempts += 1
        runtime.next_poll_at = current + timedelta(seconds=self.POLL_INTERVAL_SECONDS)
        runtime.last_poll_result = "polling"
        runtime.last_poll_error = None

        request = urllib.request.Request(
            f"{self.CODES_ENDPOINT}/{runtime.code}",
            headers={
                "Accept": "application/json",
                "User-Agent": "kilo/skill-runner",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = _http_status(response)
                if status == 202:
                    runtime.last_poll_result = "pending"
                    return False
                payload = _load_json_response(
                    response=response,
                    operation="Kilo device auth poll",
                )
                if status == 202 or str(payload.get("status") or "").strip().lower() == "pending":
                    runtime.last_poll_result = "pending"
                    return False
        except urllib.error.HTTPError as exc:
            body = _read_http_error_body(exc)
            if exc.code == 202:
                runtime.last_poll_result = "pending"
                return False
            if exc.code == 403:
                runtime.last_poll_result = "denied"
                runtime.last_poll_error = "denied"
                raise RuntimeError("Authorization denied") from exc
            if exc.code == 410:
                runtime.last_poll_result = "expired"
                runtime.last_poll_error = "expired"
                raise RuntimeError("Authorization expired") from exc
            detail = _body_preview(body)
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = detail
            raise RuntimeError(f"Kilo auth poll failed: {exc.code} {exc.reason}. Response: {detail}") from exc
        except RuntimeError:
            raise
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = _redact(str(exc))
            raise RuntimeError(f"Kilo auth poll failed: {_redact(str(exc))}") from exc

        token = self._optional_string(payload.get("token"))
        if token is None:
            detail = self._describe_payload(payload)
            runtime.last_poll_result = "failed"
            runtime.last_poll_error = detail
            raise RuntimeError(f"Kilo approved response missing token: {detail}")

        email = self._optional_string(payload.get("userEmail"))
        expires_at_ms = int((current + timedelta(days=self.TOKEN_TTL_DAYS)).timestamp() * 1000)
        self._upsert_oauth(token=token, expires_at_ms=expires_at_ms, account_id=email)
        runtime.completed = True
        runtime.updated_at = current
        runtime.last_poll_result = "succeeded"
        runtime.last_poll_error = None
        return True

    def _read_auth_payload(self) -> dict[str, Any]:
        if not self.auth_path.exists():
            return {}
        raw = self.auth_path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}

    def _write_auth_payload(self, payload: dict[str, Any]) -> None:
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        tmp_path = ""
        with NamedTemporaryFile("w", delete=False, dir=str(self.auth_path.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            os.replace(tmp_path, self.auth_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _upsert_oauth(
        self,
        *,
        token: str,
        expires_at_ms: int,
        account_id: str | None = None,
    ) -> None:
        payload = self._read_auth_payload()
        entry: dict[str, Any] = {
            "type": "oauth",
            "access": token,
            "refresh": token,
            "expires": expires_at_ms,
        }
        if account_id:
            entry["accountId"] = account_id
        payload["kilo"] = entry
        self._write_auth_payload(payload)

    def _required_string(self, payload: dict[str, Any], key: str) -> str:
        value = self._optional_string(payload.get(key))
        if value is None:
            raise RuntimeError(f"Kilo device code response missing {key}")
        return value

    def _optional_string(self, value: Any) -> str | None:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    def _positive_int(self, value: Any, *, default: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return default
        return parsed if parsed > 0 else default

    def _describe_payload(self, payload: dict[str, Any]) -> str:
        safe = {
            key: ("<redacted>" if key.lower() in {"token", "access", "refresh", "apikey", "api_key"} else value)
            for key, value in payload.items()
        }
        return _body_preview(json.dumps(safe, ensure_ascii=False, sort_keys=True))
