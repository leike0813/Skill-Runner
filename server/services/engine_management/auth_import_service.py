from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.engines.opencode.auth.provider_registry import opencode_auth_provider_registry
from server.runtime.adapter.common.profile_loader import CredentialImportProfile, load_adapter_profile
from server.services.engine_management.auth_import_validator_registry import (
    AuthImportValidationError,
    auth_import_validator_registry,
)
from server.services.engine_management.runtime_profile import get_runtime_profile


class AuthImportError(ValueError):
    """Raised when auth import request is invalid."""


@dataclass(frozen=True)
class _RuleSelection:
    required: tuple[CredentialImportProfile, ...]
    optional: tuple[CredentialImportProfile, ...]


class AuthImportService:
    def __init__(self) -> None:
        self._runtime_profile = get_runtime_profile()

    def _adapter_profile_path(self, engine: str) -> Path:
        normalized_engine = engine.strip().lower()
        return (
            Path(__file__).resolve().parents[2]
            / "engines"
            / normalized_engine
            / "adapter"
            / "adapter_profile.json"
        )

    def _load_profile(self, engine: str):
        normalized_engine = engine.strip().lower()
        if normalized_engine not in {"codex", "gemini", "iflow", "opencode"}:
            raise AuthImportError(f"Unsupported engine: {engine}")
        return load_adapter_profile(normalized_engine, self._adapter_profile_path(normalized_engine))

    def _normalize_provider(self, provider_id: str | None) -> str | None:
        if not isinstance(provider_id, str):
            return None
        normalized = provider_id.strip().lower()
        return normalized or None

    def _select_rules(
        self,
        *,
        engine: str,
        provider_id: str | None,
    ) -> _RuleSelection:
        profile = self._load_profile(engine)
        imports = {rule.source: rule for rule in profile.cli_management.credential_imports}
        normalized_engine = profile.engine
        if normalized_engine != "opencode":
            required_sources = profile.cli_management.credential_policy.sources
            required_rules: list[CredentialImportProfile] = []
            for source in required_sources:
                rule = imports.get(source)
                if rule is None:
                    raise AuthImportError(
                        f"Engine `{normalized_engine}` missing import rule for required file: {source}"
                    )
                required_rules.append(rule)
            optional_rules = [
                rule
                for source, rule in imports.items()
                if source not in set(required_sources)
            ]
            return _RuleSelection(
                required=tuple(required_rules),
                optional=tuple(optional_rules),
            )

        normalized_provider = self._normalize_provider(provider_id)
        if normalized_provider is None:
            raise AuthImportError("provider_id is required for opencode auth import")
        provider = opencode_auth_provider_registry.get(normalized_provider)
        if provider.auth_mode != "oauth":
            raise AuthImportError(
                f"opencode provider `{normalized_provider}` does not support import auth"
            )

        auth_rule = imports.get("auth.json")
        if auth_rule is None:
            raise AuthImportError("opencode adapter profile missing auth.json import rule")
        if normalized_provider == "google":
            google_optional_rules: list[CredentialImportProfile] = []
            antigravity_rule = imports.get("antigravity-accounts.json")
            if antigravity_rule is not None:
                google_optional_rules.append(antigravity_rule)
            return _RuleSelection(required=(auth_rule,), optional=tuple(google_optional_rules))
        return _RuleSelection(required=(auth_rule,), optional=tuple())

    def _resolve_target_path(self, target_relpath: str) -> Path:
        candidate = (self._runtime_profile.agent_home / target_relpath).resolve()
        agent_home = self._runtime_profile.agent_home.resolve()
        if agent_home not in candidate.parents and candidate != agent_home:
            raise AuthImportError(f"target path escapes agent_home: {target_relpath}")
        return candidate

    def _find_uploaded_content(
        self,
        *,
        files: dict[str, bytes],
        rule: CredentialImportProfile,
    ) -> tuple[str, bytes] | None:
        accepted_names = [rule.source, *rule.aliases]
        for accepted in accepted_names:
            payload = files.get(accepted)
            if payload is not None:
                return accepted, payload
        return None

    def _write_file(self, *, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def _parse_json_object(self, name: str, content: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthImportValidationError(f"{name} must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise AuthImportValidationError(f"{name} must be a JSON object")
        return payload

    def _convert_codex_auth_to_opencode_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        tokens_obj = payload.get("tokens")
        tokens = tokens_obj if isinstance(tokens_obj, dict) else {}
        refresh = tokens.get("refresh_token")
        access = tokens.get("access_token")
        if not isinstance(refresh, str) or not refresh.strip():
            raise AuthImportValidationError("Codex auth.json missing tokens.refresh_token")
        if not isinstance(access, str) or not access.strip():
            raise AuthImportValidationError("Codex auth.json missing tokens.access_token")
        now_ms = int(time.time() * 1000)
        converted: dict[str, Any] = {
            "type": "oauth",
            "refresh": refresh.strip(),
            "access": access.strip(),
            "expires": now_ms + 3600 * 1000,
        }
        account_id = tokens.get("account_id")
        if isinstance(account_id, str) and account_id.strip():
            converted["accountId"] = account_id.strip()
        return converted

    def _load_opencode_existing_auth(self, *, target_path: Path) -> dict[str, Any]:
        if not target_path.exists():
            return {}
        raw = target_path.read_bytes()
        if not raw.strip():
            return {}
        parsed = self._parse_json_object(str(target_path), raw)
        return parsed

    def _extract_opencode_provider_entry(
        self,
        *,
        provider_id: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        payload = self._parse_json_object(filename, content)
        existing_obj = payload.get(provider_id)
        if isinstance(existing_obj, dict):
            if existing_obj.get("type") != "oauth":
                raise AuthImportValidationError(
                    f"{filename} provider `{provider_id}` must include oauth type entry"
                )
            return existing_obj
        # Codex auth.json compatibility: convert into OpenCode OpenAI entry.
        if provider_id == "openai" and isinstance(payload.get("tokens"), dict):
            return self._convert_codex_auth_to_opencode_openai(payload)
        raise AuthImportValidationError(
            f"{filename} does not contain oauth entry for provider `{provider_id}`"
        )

    def _prepare_opencode_auth_content(
        self,
        *,
        provider_id: str,
        filename: str,
        content: bytes,
        target_path: Path,
    ) -> bytes:
        provider_entry = self._extract_opencode_provider_entry(
            provider_id=provider_id,
            filename=filename,
            content=content,
        )
        merged_payload = self._load_opencode_existing_auth(target_path=target_path)
        merged_payload[provider_id] = provider_entry
        return json.dumps(merged_payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"

    def get_import_spec(self, *, engine: str, provider_id: str | None = None) -> dict[str, Any]:
        profile = self._load_profile(engine)
        selection = self._select_rules(engine=engine, provider_id=provider_id)
        normalized_provider = self._normalize_provider(provider_id)
        required_items: list[dict[str, Any]] = []
        optional_items: list[dict[str, Any]] = []

        def _build_item(rule: CredentialImportProfile) -> dict[str, Any]:
            default_hint = f"$HOME/{rule.target_relpath}" if rule.target_relpath.startswith(".") else rule.target_relpath
            return {
                "filename": rule.source,
                "aliases": list(rule.aliases),
                "default_path_hint": default_hint,
                "target_relpath": rule.target_relpath,
                "import_validator": rule.import_validator,
            }

        for rule in selection.required:
            required_items.append(_build_item(rule))
        for rule in selection.optional:
            optional_items.append(_build_item(rule))

        supported = True
        if profile.engine == "opencode":
            if normalized_provider is None:
                supported = False
            else:
                provider = opencode_auth_provider_registry.get(normalized_provider)
                supported = provider.auth_mode == "oauth"

        return {
            "engine": profile.engine,
            "provider_id": normalized_provider,
            "supported": supported,
            "required_files": required_items,
            "optional_files": optional_items,
            "risk_notice_required": profile.engine == "opencode" and normalized_provider == "google",
        }

    def import_auth_files(
        self,
        *,
        engine: str,
        files: dict[str, bytes],
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_engine = engine.strip().lower()
        if not files:
            raise AuthImportError("No files uploaded")
        profile = self._load_profile(normalized_engine)
        normalized_provider = self._normalize_provider(provider_id)
        selection = self._select_rules(engine=normalized_engine, provider_id=normalized_provider)
        imported: list[dict[str, Any]] = []
        matched: dict[str, tuple[str, bytes]] = {}

        for rule in (*selection.required, *selection.optional):
            found = self._find_uploaded_content(files=files, rule=rule)
            if found is not None:
                matched[rule.source] = found

        missing_required = [
            rule.source for rule in selection.required if rule.source not in matched
        ]
        if missing_required:
            raise AuthImportError(f"Missing required files: {', '.join(missing_required)}")

        for rule in selection.required:
            source_name, content = matched[rule.source]
            auth_import_validator_registry.validate(
                validator=rule.import_validator,
                filename=source_name,
                content=content,
            )
            target_path = self._resolve_target_path(rule.target_relpath)
            bytes_to_write = content
            if profile.engine == "opencode" and rule.source == "auth.json":
                if normalized_provider is None:
                    raise AuthImportError("provider_id is required for opencode auth import")
                bytes_to_write = self._prepare_opencode_auth_content(
                    provider_id=normalized_provider,
                    filename=source_name,
                    content=content,
                    target_path=target_path,
                )
            self._write_file(path=target_path, content=bytes_to_write)
            imported.append(
                {
                    "source": source_name,
                    "target_relpath": rule.target_relpath,
                    "target_path": str(target_path),
                    "required": True,
                }
            )

        for rule in selection.optional:
            found = matched.get(rule.source)
            if found is None:
                continue
            source_name, content = found
            auth_import_validator_registry.validate(
                validator=rule.import_validator,
                filename=source_name,
                content=content,
            )
            target_path = self._resolve_target_path(rule.target_relpath)
            self._write_file(path=target_path, content=content)
            imported.append(
                {
                    "source": source_name,
                    "target_relpath": rule.target_relpath,
                    "target_path": str(target_path),
                    "required": False,
                }
            )

        return {
            "engine": profile.engine,
            "provider_id": normalized_provider,
            "imported_files": imported,
            "risk_notice_required": profile.engine == "opencode" and normalized_provider == "google",
        }


auth_import_service = AuthImportService()
