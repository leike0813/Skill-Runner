from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


class AuthImportValidationError(ValueError):
    """Raised when imported auth payload fails structural validation."""


def _require_json_object(name: str, content: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthImportValidationError(f"{name} must be valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise AuthImportValidationError(f"{name} must be a JSON object")
    return parsed


def _validate_codex_auth_json(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    tokens = payload.get("tokens")
    api_key = payload.get("OPENAI_API_KEY")
    refresh_token = tokens.get("refresh_token") if isinstance(tokens, dict) else None
    access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
    has_token_bundle = (
        isinstance(tokens, dict)
        and isinstance(refresh_token, str)
        and bool(refresh_token.strip())
        and isinstance(access_token, str)
        and bool(access_token.strip())
    )
    has_api_key = isinstance(api_key, str) and bool(api_key.strip())
    if not has_token_bundle and not has_api_key:
        raise AuthImportValidationError(
            f"{name} must contain Codex oauth tokens or OPENAI_API_KEY"
        )


def _validate_json_object(name: str, content: bytes) -> None:
    _require_json_object(name, content)


def _validate_gemini_accounts(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if "accounts" not in payload and "active" not in payload:
        raise AuthImportValidationError(
            f"{name} must contain Gemini account metadata (accounts/active)"
        )


def _validate_gemini_oauth_creds(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if "refresh_token" not in payload and "tokens" not in payload:
        raise AuthImportValidationError(
            f"{name} must contain oauth credential fields (refresh_token/tokens)"
        )


def _validate_iflow_accounts(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if "accounts" not in payload and "active" not in payload:
        raise AuthImportValidationError(
            f"{name} must contain iFlow account metadata (accounts/active)"
        )


def _validate_iflow_oauth_creds(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if "refresh_token" not in payload and "tokens" not in payload:
        raise AuthImportValidationError(
            f"{name} must contain oauth credential fields (refresh_token/tokens)"
        )


def _validate_opencode_auth(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if payload.get("tokens") is not None:
        # Codex-style auth.json is accepted and converted later.
        return
    has_provider_entry = any(
        isinstance(value, dict)
        and isinstance(value.get("type"), str)
        and value.get("type") in {"oauth", "api"}
        for value in payload.values()
    )
    if not has_provider_entry:
        raise AuthImportValidationError(
            f"{name} must contain provider entries in OpenCode auth format"
        )


def _validate_opencode_antigravity_accounts(name: str, content: bytes) -> None:
    payload = _require_json_object(name, content)
    if "accounts" not in payload:
        raise AuthImportValidationError(
            f"{name} must contain antigravity accounts field: accounts"
        )


ValidatorFn = Callable[[str, bytes], None]


@dataclass(frozen=True)
class AuthImportValidatorRegistry:
    _validators: dict[str, ValidatorFn]

    def validate(self, *, validator: str | None, filename: str, content: bytes) -> None:
        if validator is None or not validator.strip():
            return
        fn = self._validators.get(validator.strip())
        if fn is None:
            raise AuthImportValidationError(f"Unsupported import validator: {validator}")
        fn(filename, content)


auth_import_validator_registry = AuthImportValidatorRegistry(
    _validators={
        "json_object": _validate_json_object,
        "codex_auth_json": _validate_codex_auth_json,
        "gemini_google_accounts_json": _validate_gemini_accounts,
        "gemini_oauth_creds_json": _validate_gemini_oauth_creds,
        "iflow_accounts_json": _validate_iflow_accounts,
        "iflow_oauth_creds_json": _validate_iflow_oauth_creds,
        "opencode_auth_json": _validate_opencode_auth,
        "opencode_antigravity_accounts_json": _validate_opencode_antigravity_accounts,
    }
)
