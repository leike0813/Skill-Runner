from __future__ import annotations

import base64
import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from server.config import config
from server.engines.codebuddy.auth.provider_registry import require_provider
from server.engines.codebuddy.storage_layout import (
    assert_no_symlink,
    atomic_write_json,
    credential_vault_path,
    ensure_private_dir,
    provider_runtime_dir,
    runtime_root,
)


VAULT_VERSION = 1


@dataclass(frozen=True)
class CodeBuddyCredential:
    token: str
    user_id: str
    updated_at: str
    expires_at_advisory: str | None
    sdk_version: str
    cli_version: str | None


@dataclass(frozen=True)
class CodeBuddyCredentialStatus:
    provider_id: str
    credential_state: str
    updated_at: str | None
    expires_at_advisory: str | None


class CodeBuddyCredentialStore:
    """Provider-keyed local vault whose public surface never exposes tokens."""

    def __init__(
        self,
        *,
        path: Path | None = None,
        agent_home: Path | None = None,
    ) -> None:
        self.path = path or credential_vault_path()
        self.agent_home = agent_home or Path(config.SYSTEM.AGENT_HOME)
        self._lock = threading.RLock()

    def get(self, provider_id: str) -> CodeBuddyCredential | None:
        provider = require_provider(provider_id)
        with self._lock:
            raw = self._read_providers().get(provider.provider_id)
        return self._parse_credential(raw)

    def put(
        self,
        provider_id: str,
        *,
        token: str,
        user_id: str,
        expires_at_advisory: str | None = None,
        sdk_version: str = "0.3.205",
        cli_version: str | None = None,
    ) -> CodeBuddyCredentialStatus:
        provider = require_provider(provider_id)
        clean_token = token.strip()
        clean_user_id = user_id.strip()
        if not clean_token:
            raise ValueError("CodeBuddy credential token is required")
        if not clean_user_id:
            raise ValueError("CodeBuddy credential user_id is required")
        expiry = expires_at_advisory or _jwt_advisory_expiry(clean_token)
        credential = CodeBuddyCredential(
            token=clean_token,
            user_id=clean_user_id,
            updated_at=_utc_now(),
            expires_at_advisory=expiry,
            sdk_version=sdk_version,
            cli_version=cli_version,
        )
        with self._lock:
            providers = self._read_providers()
            previous = self._parse_credential(providers.get(provider.provider_id))
            if (
                previous is not None
                and previous.token == credential.token
                and previous.user_id == credential.user_id
                and previous.expires_at_advisory == credential.expires_at_advisory
                and previous.sdk_version == credential.sdk_version
                and previous.cli_version == credential.cli_version
            ):
                return self.project_status(provider.provider_id)
            providers[provider.provider_id] = asdict(credential)
            self._write_providers(providers)
            if previous is not None and (
                previous.user_id != credential.user_id or previous.token != credential.token
            ):
                self._rotate_provider_state(provider.provider_id)
        return self.project_status(provider.provider_id)

    def delete(self, provider_id: str) -> bool:
        provider = require_provider(provider_id)
        with self._lock:
            providers = self._read_providers()
            deleted = providers.pop(provider.provider_id, None) is not None
            if deleted:
                self._write_providers(providers)
            self._rotate_provider_state(provider.provider_id)
        return deleted

    def project_status(self, provider_id: str) -> CodeBuddyCredentialStatus:
        provider = require_provider(provider_id)
        credential = self.get(provider.provider_id)
        if credential is None:
            return CodeBuddyCredentialStatus(
                provider_id=provider.provider_id,
                credential_state="missing",
                updated_at=None,
                expires_at_advisory=None,
            )
        state = "expired" if _is_advisory_expired(credential.expires_at_advisory) else "present"
        return CodeBuddyCredentialStatus(
            provider_id=provider.provider_id,
            credential_state=state,
            updated_at=credential.updated_at,
            expires_at_advisory=credential.expires_at_advisory,
        )

    def project_all_statuses(self) -> tuple[CodeBuddyCredentialStatus, ...]:
        from server.engines.codebuddy.auth.provider_registry import CODEBUDDY_PROVIDER_IDS

        return tuple(self.project_status(provider_id) for provider_id in CODEBUDDY_PROVIDER_IDS)

    def _read_providers(self) -> dict[str, Mapping[str, Any]]:
        path = self.path
        if not path.exists():
            return {}
        self._assert_safe_path(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("CodeBuddy credential vault is unreadable") from exc
        if not isinstance(payload, dict) or payload.get("version") != VAULT_VERSION:
            raise ValueError("CodeBuddy credential vault version must be 1")
        providers = payload.get("providers")
        if not isinstance(providers, dict):
            raise ValueError("CodeBuddy credential vault providers must be an object")
        return {
            str(key): value
            for key, value in providers.items()
            if isinstance(key, str) and isinstance(value, Mapping)
        }

    def _write_providers(self, providers: Mapping[str, Mapping[str, Any]]) -> None:
        path = self.path
        parent = ensure_private_dir(path.parent)
        payload = {
            "version": VAULT_VERSION,
            "providers": dict(providers),
        }
        atomic_write_json(path, payload)

    def _rotate_provider_state(self, provider_id: str) -> None:
        provider = require_provider(provider_id)
        root = runtime_root(self.agent_home)
        target = provider_runtime_dir(provider.provider_id, self.agent_home)
        assert_no_symlink(root)
        assert_no_symlink(target)
        if target.exists():
            shutil.rmtree(target)
        ensure_private_dir(root)

    @staticmethod
    def _assert_safe_path(path: Path) -> None:
        assert_no_symlink(path)

    @staticmethod
    def _parse_credential(raw: Mapping[str, Any] | None) -> CodeBuddyCredential | None:
        if not isinstance(raw, Mapping):
            return None
        required = ("token", "user_id", "updated_at", "sdk_version")
        if any(not isinstance(raw.get(key), str) or not str(raw[key]).strip() for key in required):
            raise ValueError("CodeBuddy credential entry is invalid")
        expiry = raw.get("expires_at_advisory")
        cli_version = raw.get("cli_version")
        return CodeBuddyCredential(
            token=str(raw["token"]),
            user_id=str(raw["user_id"]),
            updated_at=str(raw["updated_at"]),
            expires_at_advisory=str(expiry) if isinstance(expiry, str) else None,
            sdk_version=str(raw["sdk_version"]),
            cli_version=str(cli_version) if isinstance(cli_version, str) else None,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_advisory_expired(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)


def _jwt_advisory_expiry(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        payload = json.loads(payload_bytes.decode("utf-8"))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


codebuddy_credential_store = CodeBuddyCredentialStore()
