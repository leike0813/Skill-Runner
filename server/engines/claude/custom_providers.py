from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from server.services.engine_management.runtime_profile import get_runtime_profile


@dataclass(frozen=True)
class ClaudeCustomProvider:
    provider_id: str
    api_key: str
    base_url: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class ClaudeResolvedCustomModel:
    provider_id: str
    model: str
    api_key: str
    base_url: str


class ClaudeCustomProviderStore:
    def __init__(self, config_path: Path | None = None) -> None:
        runtime_profile = get_runtime_profile()
        self._config_path = config_path or (runtime_profile.agent_home / ".claude" / "custom_providers.json")
        self._lock = RLock()

    @property
    def config_path(self) -> Path:
        return self._config_path

    def list_providers(self) -> list[ClaudeCustomProvider]:
        payload = self._load_payload()
        rows = payload.get("providers")
        providers: list[ClaudeCustomProvider] = []
        if not isinstance(rows, list):
            return providers
        for row in rows:
            normalized = self._normalize_provider_payload(row)
            if normalized is not None:
                providers.append(normalized)
        providers.sort(key=lambda item: item.provider_id)
        return providers

    def upsert_provider(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        models: list[str],
    ) -> ClaudeCustomProvider:
        normalized = self._normalize_provider_fields(
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
            models=models,
        )
        payload = self._load_payload()
        rows = payload.get("providers")
        current = rows if isinstance(rows, list) else []
        next_rows: list[dict[str, Any]] = []
        replaced = False
        for row in current:
            existing = self._normalize_provider_payload(row)
            if existing is None:
                continue
            if existing.provider_id == normalized.provider_id:
                next_rows.append(self._to_payload_row(normalized))
                replaced = True
            else:
                next_rows.append(self._to_payload_row(existing))
        if not replaced:
            next_rows.append(self._to_payload_row(normalized))
        next_rows.sort(key=lambda item: str(item.get("provider_id") or ""))
        self._write_payload({"providers": next_rows})
        return normalized

    def delete_provider(self, provider_id: str) -> bool:
        normalized_provider_id = self._normalize_provider_id(provider_id)
        payload = self._load_payload()
        rows = payload.get("providers")
        current = rows if isinstance(rows, list) else []
        next_rows: list[dict[str, Any]] = []
        removed = False
        for row in current:
            existing = self._normalize_provider_payload(row)
            if existing is None:
                continue
            if existing.provider_id == normalized_provider_id:
                removed = True
                continue
            next_rows.append(self._to_payload_row(existing))
        if removed:
            self._write_payload({"providers": next_rows})
        return removed

    def resolve_model(self, model_spec: str) -> ClaudeResolvedCustomModel | None:
        normalized_model_spec = model_spec.strip()
        if "/" not in normalized_model_spec:
            return None
        provider_part, model_part = normalized_model_spec.split("/", 1)
        provider_id = self._normalize_provider_id(provider_part)
        model_name = self._normalize_model_name(model_part)
        base_model_name, has_1m_suffix = self._strip_1m_suffix(model_name)
        for provider in self.list_providers():
            if provider.provider_id != provider_id:
                continue
            if model_name in provider.models:
                return ClaudeResolvedCustomModel(
                    provider_id=provider.provider_id,
                    model=base_model_name,
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                )
            if has_1m_suffix and base_model_name in provider.models:
                return ClaudeResolvedCustomModel(
                    provider_id=provider.provider_id,
                    model=base_model_name,
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                )
        return None

    def list_model_specs(self) -> list[str]:
        result: list[str] = []
        for provider in self.list_providers():
            for model in provider.models:
                result.append(f"{provider.provider_id}/{model}")
        result.sort()
        return result

    def _load_payload(self) -> dict[str, Any]:
        path = self._config_path
        with self._lock:
            if not path.exists():
                return {"providers": []}
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                self._backup_invalid_file(path)
                self._write_payload({"providers": []})
                return {"providers": []}
            if not isinstance(payload, dict):
                self._backup_invalid_file(path)
                self._write_payload({"providers": []})
                return {"providers": []}
            return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        path = self._config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                prefix=f"{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                temp_path = Path(handle.name)
            temp_path.replace(path)

    def _backup_invalid_file(self, path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_name(f"{path.name}.invalid.bak")
        try:
            shutil.copy2(path, backup)
        except OSError:
            return

    def _normalize_provider_payload(self, raw: Any) -> ClaudeCustomProvider | None:
        if not isinstance(raw, dict):
            return None
        provider_id = raw.get("provider_id")
        api_key = raw.get("api_key")
        base_url = raw.get("base_url")
        models = raw.get("models")
        if not isinstance(models, list):
            return None
        try:
            return self._normalize_provider_fields(
                provider_id=str(provider_id or ""),
                api_key=str(api_key or ""),
                base_url=str(base_url or ""),
                models=[str(item) for item in models],
            )
        except ValueError:
            return None

    def _normalize_provider_fields(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        models: list[str],
    ) -> ClaudeCustomProvider:
        normalized_provider_id = self._normalize_provider_id(provider_id)
        normalized_api_key = api_key.strip()
        normalized_base_url = base_url.strip()
        if not normalized_api_key:
            raise ValueError("api_key must be non-empty")
        if not normalized_base_url:
            raise ValueError("base_url must be non-empty")
        normalized_models = tuple(dict.fromkeys(self._normalize_model_name(item) for item in models))
        if not normalized_models:
            raise ValueError("models must not be empty")
        return ClaudeCustomProvider(
            provider_id=normalized_provider_id,
            api_key=normalized_api_key,
            base_url=normalized_base_url,
            models=normalized_models,
        )

    def _normalize_provider_id(self, provider_id: str) -> str:
        normalized = provider_id.strip().lower()
        if not normalized:
            raise ValueError("provider_id must be non-empty")
        if "/" in normalized:
            raise ValueError("provider_id must not contain '/'")
        return normalized

    def _normalize_model_name(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model name must be non-empty")
        if "/" in normalized:
            raise ValueError("model name must not contain '/'")
        return normalized

    def _strip_1m_suffix(self, value: str) -> tuple[str, bool]:
        normalized = value.strip()
        stripped = normalized.replace("[1m]", "").strip()
        return stripped, stripped != normalized

    def _to_payload_row(self, provider: ClaudeCustomProvider) -> dict[str, Any]:
        return {
            "provider_id": provider.provider_id,
            "api_key": provider.api_key,
            "base_url": provider.base_url,
            "models": list(provider.models),
        }


claude_custom_provider_store = ClaudeCustomProviderStore()
