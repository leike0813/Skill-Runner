from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from server.engines.claude.custom_providers import ClaudeResolvedCustomModel, claude_custom_provider_store


@dataclass(frozen=True)
class EngineCustomProviderRecord:
    provider_id: str
    api_key: str
    base_url: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedCustomProviderModel:
    provider_id: str
    model: str
    api_key: str
    base_url: str


@dataclass(frozen=True)
class EngineCustomProviderModelEntry:
    id: str
    display_name: str
    provider: str
    model: str
    source: str = "custom_provider"


class EngineCustomProviderBackend(Protocol):
    def list_providers(self) -> list[EngineCustomProviderRecord]:
        ...

    def upsert_provider(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        models: list[str],
    ) -> EngineCustomProviderRecord:
        ...

    def delete_provider(self, provider_id: str) -> bool:
        ...

    def resolve_model(self, model_spec: str) -> ResolvedCustomProviderModel | None:
        ...

    def list_model_entries(self) -> list[EngineCustomProviderModelEntry]:
        ...


class _ClaudeBackend:
    def list_providers(self) -> list[EngineCustomProviderRecord]:
        return [
            EngineCustomProviderRecord(
                provider_id=item.provider_id,
                api_key=item.api_key,
                base_url=item.base_url,
                models=item.models,
            )
            for item in claude_custom_provider_store.list_providers()
        ]

    def upsert_provider(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        models: list[str],
    ) -> EngineCustomProviderRecord:
        item = claude_custom_provider_store.upsert_provider(
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
            models=models,
        )
        return EngineCustomProviderRecord(
            provider_id=item.provider_id,
            api_key=item.api_key,
            base_url=item.base_url,
            models=item.models,
        )

    def delete_provider(self, provider_id: str) -> bool:
        return claude_custom_provider_store.delete_provider(provider_id)

    def resolve_model(self, model_spec: str) -> ResolvedCustomProviderModel | None:
        resolved: ClaudeResolvedCustomModel | None = claude_custom_provider_store.resolve_model(model_spec)
        if resolved is None:
            return None
        return ResolvedCustomProviderModel(
            provider_id=resolved.provider_id,
            model=resolved.model,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

    def list_model_entries(self) -> list[EngineCustomProviderModelEntry]:
        rows: list[EngineCustomProviderModelEntry] = []
        for provider in claude_custom_provider_store.list_providers():
            for model in provider.models:
                rows.append(
                    EngineCustomProviderModelEntry(
                        id=f"{provider.provider_id}/{model}",
                        display_name=f"{provider.provider_id}/{model}",
                        provider=provider.provider_id,
                        model=model,
                    )
                )
        rows.sort(key=lambda item: item.id)
        return rows


class EngineCustomProviderService:
    def __init__(self) -> None:
        self._backends: dict[str, EngineCustomProviderBackend] = {
            "claude": _ClaudeBackend(),
        }

    def supports(self, engine: str) -> bool:
        return engine.strip().lower() in self._backends

    def list_providers(self, engine: str) -> list[EngineCustomProviderRecord]:
        backend = self._backend_for(engine)
        if backend is None:
            return []
        return backend.list_providers()

    def upsert_provider(
        self,
        *,
        engine: str,
        provider_id: str,
        api_key: str,
        base_url: str,
        models: list[str],
    ) -> EngineCustomProviderRecord:
        backend = self._require_backend(engine)
        return backend.upsert_provider(
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
            models=models,
        )

    def delete_provider(self, *, engine: str, provider_id: str) -> bool:
        backend = self._require_backend(engine)
        return backend.delete_provider(provider_id)

    def resolve_model(self, engine: str, model_spec: str) -> ResolvedCustomProviderModel | None:
        backend = self._backend_for(engine)
        if backend is None:
            return None
        return backend.resolve_model(model_spec)

    def list_model_entries(self, engine: str) -> list[EngineCustomProviderModelEntry]:
        backend = self._backend_for(engine)
        if backend is None:
            return []
        return backend.list_model_entries()

    def _backend_for(self, engine: str) -> EngineCustomProviderBackend | None:
        return self._backends.get(engine.strip().lower())

    def _require_backend(self, engine: str) -> EngineCustomProviderBackend:
        backend = self._backend_for(engine)
        if backend is None:
            raise ValueError(f"Engine '{engine}' does not support custom providers")
        return backend


engine_custom_provider_service = EngineCustomProviderService()
