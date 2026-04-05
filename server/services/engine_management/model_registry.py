import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from server.config import config
from server.runtime.adapter.common.profile_loader import AdapterProfile, load_adapter_profile
from server.services.engine_management.engine_custom_provider_service import (
    EngineCustomProviderModelEntry,
    engine_custom_provider_service,
)
from server.services.engine_management.engine_status_cache_service import engine_status_cache_service
from server.services.engine_management.engine_model_catalog_lifecycle import (
    engine_model_catalog_lifecycle,
)
from server.services.engine_management.engine_catalog import supported_engines as _supported_engine_catalog

logger = logging.getLogger(__name__)

def supported_engines() -> List[str]:
    return list(_supported_engine_catalog())


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: Optional[str]
    deprecated: bool
    notes: Optional[str]
    supported_effort: Optional[List[str]]
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None
    source: str = "official"


@dataclass(frozen=True)
class ModelCatalog:
    engine: str
    cli_version_detected: Optional[str]
    snapshot_version_used: Optional[str]
    fallback_reason: Optional[str]
    models: List[ModelEntry]
    source: str = "pinned_snapshot"


@dataclass(frozen=True)
class NormalizedModelSelection:
    engine: str
    provider_id: str | None
    model: str | None
    model_id: str | None
    runtime_model: str | None
    requested_effort: str
    effective_effort: str | None
    supported_effort: List[str]


class ModelRegistry:
    def __init__(self) -> None:
        self._cache: Dict[str, ModelCatalog] = {}
        self._adapter_profiles: Dict[str, AdapterProfile] = {}

    def list_engines(self) -> List[Dict[str, Optional[str]]]:
        return [
            {"engine": engine, "cli_version_detected": engine_status_cache_service.get_engine_version(engine)}
            for engine in self._supported_engines()
        ]

    def supports_model_snapshots(self, engine: str) -> bool:
        return not self._uses_runtime_probe_catalog(engine)

    def supports_runtime_catalog_refresh(self, engine: str) -> bool:
        return self._uses_runtime_probe_catalog(engine)

    def get_models(self, engine: str, refresh: bool = False) -> ModelCatalog:
        if engine not in self._supported_engines():
            raise ValueError(f"Unknown engine: {engine}")

        if self._uses_runtime_probe_catalog(engine):
            catalog = self._get_runtime_probe_models(engine, refresh=refresh)
            self._cache[engine] = catalog
            return catalog

        if not refresh and engine in self._cache:
            return self._cache[engine]

        cli_version = engine_status_cache_service.get_engine_version(engine)
        manifest = self._load_manifest(engine)
        snapshots = self._extract_snapshots(manifest)
        snapshot_version, fallback_reason = self._select_snapshot_version(
            cli_version,
            [snap["version"] for snap in snapshots]
        )
        snapshot_file = self._snapshot_file(manifest, snapshot_version)
        models = self._build_manifest_models(engine, snapshot_file)

        catalog = ModelCatalog(
            engine=engine,
            cli_version_detected=cli_version,
            snapshot_version_used=snapshot_version,
            fallback_reason=fallback_reason,
            models=models,
            source="pinned_snapshot",
        )
        self._cache[engine] = catalog
        return catalog

    def refresh(self, engine: Optional[str] = None) -> None:
        if engine is None:
            self._cache.clear()
            engine_model_catalog_lifecycle.request_refresh_async_all(reason="registry_refresh_all")
            return
        self._cache.pop(engine, None)
        if engine in self._supported_engines() and self._uses_runtime_probe_catalog(engine):
            engine_model_catalog_lifecycle.request_refresh_async(engine, reason="registry_refresh")

    def get_manifest_view(self, engine: str) -> Dict[str, Any]:
        if engine not in self._supported_engines():
            raise ValueError(f"Unknown engine: {engine}")

        if self._uses_runtime_probe_catalog(engine):
            return self._build_runtime_probe_manifest_view(engine)

        cli_version = engine_status_cache_service.get_engine_version(engine)
        manifest = self._load_manifest(engine)
        snapshots = self._extract_snapshots(manifest)
        snapshot_version, fallback_reason = self._select_snapshot_version(
            cli_version,
            [snap["version"] for snap in snapshots]
        )
        snapshot_file = self._snapshot_file(manifest, snapshot_version)
        models = self._build_manifest_models(engine, snapshot_file)
        return {
            "engine": engine,
            "cli_version_detected": cli_version,
            "manifest": manifest,
            "resolved_snapshot_version": snapshot_version,
            "resolved_snapshot_file": snapshot_file.name,
            "fallback_reason": fallback_reason,
            "models": [
                {
                    "id": entry.id,
                    "display_name": entry.display_name,
                    "deprecated": entry.deprecated,
                    "notes": entry.notes,
                    "supported_effort": entry.supported_effort,
                    "provider": entry.provider,
                    "provider_id": entry.provider_id,
                    "model": entry.model,
                    "source": entry.source,
                }
                for entry in models
            ],
        }

    def add_snapshot_for_detected_version(
        self,
        engine: str,
        models: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if engine not in self._supported_engines():
            raise ValueError(f"Unknown engine: {engine}")
        if self._uses_runtime_probe_catalog(engine):
            raise ValueError(f"Engine '{engine}' does not support model snapshots")

        cli_version = engine_status_cache_service.get_engine_version(engine)
        if not cli_version:
            raise ValueError(f"CLI version not detected for engine '{engine}'")

        normalized_models = self._normalize_snapshot_models(models)
        snapshot_filename = f"models_{cli_version}.json"
        models_root = self._models_root(engine)
        snapshot_path = models_root / snapshot_filename
        if snapshot_path.exists():
            raise ValueError(f"Snapshot already exists for version {cli_version}")

        manifest = self._load_manifest(engine)
        snapshots = self._extract_snapshots(manifest)
        snapshots.append({"version": cli_version, "file": snapshot_filename})
        dedup: Dict[str, str] = {}
        for snap in snapshots:
            dedup[snap["version"]] = snap["file"]
        merged = [{"version": version, "file": filename} for version, filename in dedup.items()]
        merged.sort(key=lambda item: self._semver_key(item["version"]))
        manifest["snapshots"] = merged

        snapshot_payload = {
            "engine": engine,
            "version": cli_version,
            "models": normalized_models,
        }
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_payload, f, ensure_ascii=False, indent=2)
        with open(models_root / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")

        self.refresh(engine)
        self.get_models(engine, refresh=True)
        return self.get_manifest_view(engine)

    def validate_model(self, engine: str, model_spec: str) -> Dict[str, str]:
        normalized = self.normalize_model_selection(engine, model=model_spec)
        if normalized.model is None:
            raise ValueError(f"Model '{model_spec}' not allowed for engine '{engine}'")
        payload: Dict[str, str] = {"model": normalized.model}
        if normalized.provider_id is not None:
            payload["provider_id"] = normalized.provider_id
        if normalized.runtime_model is not None and normalized.runtime_model != normalized.model:
            payload["runtime_model"] = normalized.runtime_model
        if normalized.effective_effort is not None:
            payload["model_reasoning_effort"] = normalized.effective_effort
        return payload

    def normalize_model_selection(
        self,
        engine: str,
        *,
        model: str | None = None,
        provider_id: str | None = None,
        effort: str | None = None,
    ) -> NormalizedModelSelection:
        catalog = self.get_models(engine)
        normalized_engine = engine.strip().lower()
        parsed = self._parse_model_selector(model)
        requested_effort = self._normalize_effort(effort or parsed["effort"])
        profile = self._adapter_profile(normalized_engine)
        multi_provider = profile.provider_contract.multi_provider
        canonical_provider = profile.provider_contract.canonical_provider_id
        normalized_provider = self._normalize_provider_id(provider_id or parsed["provider"])

        if not parsed["model"]:
            if multi_provider and normalized_provider is None:
                raise ValueError(f"provider_id is required for multi-provider engine '{normalized_engine}'")
            return NormalizedModelSelection(
                engine=normalized_engine,
                provider_id=normalized_provider or canonical_provider,
                model=None,
                model_id=None,
                runtime_model=None,
                requested_effort=requested_effort,
                effective_effort=None,
                supported_effort=["default"],
            )

        if multi_provider and normalized_provider is None:
            raise ValueError(f"provider_id is required for multi-provider engine '{normalized_engine}'")

        selected_model = cast(str, parsed["model"])
        entry = self._resolve_model_entry(
            engine=normalized_engine,
            models=catalog.models,
            model=selected_model,
            provider_id=normalized_provider,
        )
        if entry is None:
            unresolved = (
                f"{normalized_provider}/{selected_model}"
                if normalized_provider and multi_provider
                else selected_model
            )
            raise ValueError(f"Model '{unresolved}' not allowed for engine '{normalized_engine}'")

        effective_provider = self._effective_provider_for_entry(
            engine=normalized_engine,
            entry=entry,
            requested_provider_id=normalized_provider,
        )
        supported_effort = self._normalize_supported_effort(entry.supported_effort)
        effective_effort = self._resolve_effective_effort(
            requested_effort=requested_effort,
            supported_effort=supported_effort,
        )
        model_value = self._model_value_for_entry(entry)
        runtime_model = self._runtime_model_for_entry(
            engine=normalized_engine,
            entry=entry,
            provider_id=effective_provider,
            model=model_value,
        )
        return NormalizedModelSelection(
            engine=normalized_engine,
            provider_id=effective_provider,
            model=model_value,
            model_id=entry.id,
            runtime_model=runtime_model,
            requested_effort=requested_effort,
            effective_effort=effective_effort,
            supported_effort=supported_effort,
        )

    def _supported_engines(self) -> List[str]:
        return supported_engines()

    def _uses_runtime_probe_catalog(self, engine: str) -> bool:
        profile = self._adapter_profile(engine)
        mode = getattr(getattr(profile, "model_catalog", None), "mode", None)
        if isinstance(mode, str):
            return mode == "runtime_probe"
        return False

    def _load_manifest(self, engine: str) -> Dict[str, object]:
        profile = self._adapter_profile(engine)
        manifest_path = profile.resolve_manifest_path()
        if manifest_path is None:
            manifest_path = self._models_root(engine) / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Model manifest not found for engine '{engine}'")
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _snapshot_file(self, manifest: Dict[str, object], version: str) -> Path:
        snapshots = self._extract_snapshots(manifest)
        engine = manifest.get("engine")
        if not isinstance(engine, str):
            raise ValueError("Invalid manifest format")
        for snap in snapshots:
            if isinstance(snap, dict) and snap.get("version") == version:
                return self._models_root(engine) / snap["file"]
        raise ValueError(f"Snapshot file not found for version {version}")

    def _models_root(self, engine: str) -> Path:
        profile = self._adapter_profile(engine)
        models_root = profile.resolve_models_root()
        if models_root is None:
            return Path(config.SYSTEM.ROOT) / "server" / "engines" / engine / "models"
        return models_root

    def _adapter_profile(self, engine: str) -> AdapterProfile:
        cached = self._adapter_profiles.get(engine)
        if cached is not None:
            return cached
        profile_path = (
            Path(config.SYSTEM.ROOT) / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
        )
        loaded = load_adapter_profile(engine, profile_path)
        self._adapter_profiles[engine] = loaded
        return loaded

    def _extract_snapshots(self, manifest: Dict[str, object]) -> List[Dict[str, str]]:
        snapshots = manifest.get("snapshots")
        if not isinstance(snapshots, list):
            raise ValueError("Invalid manifest format")
        normalized: List[Dict[str, str]] = []
        for snap in snapshots:
            if not isinstance(snap, dict):
                raise ValueError("Invalid manifest format")
            version = snap.get("version")
            file = snap.get("file")
            if not isinstance(version, str) or not isinstance(file, str):
                raise ValueError("Invalid manifest format")
            normalized.append({"version": version, "file": file})
        return normalized

    def _build_manifest_models(self, engine: str, snapshot_file: Path) -> List[ModelEntry]:
        models = self._load_models(snapshot_file)
        normalized = self._normalize_catalog_models(engine, models)
        merged = self._merge_custom_provider_models(engine, normalized)
        return self._normalize_catalog_models(engine, merged)

    def _load_models(self, path: Path) -> List[ModelEntry]:
        if not path.exists():
            raise ValueError(f"Model snapshot file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        models: List[ModelEntry] = []
        for entry in payload.get("models", []):
            models.append(
                ModelEntry(
                    id=entry["id"],
                    display_name=entry.get("display_name"),
                    deprecated=entry.get("deprecated", False),
                    notes=entry.get("notes"),
                    supported_effort=entry.get("supported_effort"),
                    provider=entry.get("provider"),
                    provider_id=entry.get("provider_id"),
                    model=entry.get("model"),
                    source=str(entry.get("source") or "official"),
                )
            )
        return models

    def _normalize_catalog_models(self, engine: str, models: List[ModelEntry]) -> List[ModelEntry]:
        normalized_engine = engine.strip().lower()
        profile = self._adapter_profile(normalized_engine)
        multi_provider = profile.provider_contract.multi_provider
        canonical_provider = profile.provider_contract.canonical_provider_id
        normalized: List[ModelEntry] = []
        for item in models:
            parsed_provider, parsed_model = self._split_provider_model(item.id)
            provider = self._normalize_provider_id(item.provider_id or item.provider or parsed_provider)
            model_name = item.model.strip() if isinstance(item.model, str) and item.model.strip() else parsed_model or item.id
            if not multi_provider:
                provider = canonical_provider
            elif provider is None and normalized_engine == "claude":
                provider = "anthropic"
            normalized.append(
                ModelEntry(
                    id=item.id,
                    display_name=item.display_name,
                    deprecated=item.deprecated,
                    notes=item.notes,
                    supported_effort=self._normalize_supported_effort(item.supported_effort),
                    provider=provider,
                    provider_id=provider,
                    model=model_name,
                    source=item.source,
                )
            )
        return normalized

    def _merge_custom_provider_models(self, engine: str, models: List[ModelEntry]) -> List[ModelEntry]:
        custom_entries: list[EngineCustomProviderModelEntry] = engine_custom_provider_service.list_model_entries(engine)
        if not custom_entries:
            return models
        merged = list(models)
        seen_ids = {item.id for item in merged}
        for item in custom_entries:
            if item.id in seen_ids:
                continue
            merged.append(
                ModelEntry(
                    id=item.id,
                    display_name=item.display_name,
                    deprecated=False,
                    notes=None,
                    supported_effort=None,
                    provider=item.provider,
                    provider_id=item.provider,
                    model=item.model,
                    source=item.source,
                )
            )
            seen_ids.add(item.id)
        merged.sort(key=lambda item: item.id)
        return merged

    def _get_runtime_probe_models(self, engine: str, *, refresh: bool) -> ModelCatalog:
        if refresh:
            engine_model_catalog_lifecycle.request_refresh_async(engine, reason="api_refresh")
        snapshot_obj = engine_model_catalog_lifecycle.get_snapshot(engine)
        snapshot = snapshot_obj if isinstance(snapshot_obj, dict) else {}
        rows = snapshot.get("models")
        models: List[ModelEntry] = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                model_id = row.get("id")
                if not isinstance(model_id, str) or not model_id.strip():
                    continue
                models.append(
                    ModelEntry(
                        id=model_id.strip(),
                        display_name=row.get("display_name"),
                        deprecated=bool(row.get("deprecated", False)),
                        notes=row.get("notes"),
                        supported_effort=row.get("supported_effort"),
                        provider=row.get("provider"),
                        provider_id=row.get("provider_id"),
                        model=row.get("model"),
                        source=str(row.get("source") or "official"),
                    )
                )
        models = self._normalize_catalog_models(engine, models)
        status = snapshot.get("status")
        last_error = snapshot.get("last_error")
        fallback_reason: Optional[str] = None
        if isinstance(last_error, str) and last_error.strip():
            fallback_reason = last_error.strip()
        elif isinstance(status, str) and status not in {"ready", "runtime_probe_cache"}:
            fallback_reason = status
        updated_at = snapshot.get("updated_at")
        if isinstance(updated_at, str) and updated_at.strip():
            snapshot_version_used: Optional[str] = updated_at.strip()
        else:
            snapshot_version_used = "runtime_probe_cache"
        return ModelCatalog(
            engine=engine,
            cli_version_detected=engine_status_cache_service.get_engine_version(engine),
            snapshot_version_used=snapshot_version_used,
            fallback_reason=fallback_reason,
            models=models,
            source="runtime_probe_cache",
        )

    def _build_runtime_probe_manifest_view(self, engine: str) -> Dict[str, Any]:
        snapshot_obj = engine_model_catalog_lifecycle.get_snapshot(engine)
        snapshot = snapshot_obj if isinstance(snapshot_obj, dict) else {}
        catalog = self._get_runtime_probe_models(engine, refresh=False)
        cache_path = self._runtime_probe_cache_path(engine)
        updated_at = snapshot.get("updated_at")
        resolved_snapshot_version = (
            str(updated_at).strip()
            if isinstance(updated_at, str) and str(updated_at).strip()
            else "runtime_probe_cache"
        )
        return {
            "engine": engine,
            "cli_version_detected": catalog.cli_version_detected,
            "manifest": {
                "engine": engine,
                "dynamic": True,
                "source": "runtime_probe_cache",
                "status": snapshot.get("status"),
                "updated_at": snapshot.get("updated_at"),
                "providers": snapshot.get("providers", []),
                "last_error": snapshot.get("last_error"),
                "cache_file": cache_path.name,
                "snapshots": [],
            },
            "resolved_snapshot_version": resolved_snapshot_version,
            "resolved_snapshot_file": cache_path.name,
            "fallback_reason": catalog.fallback_reason,
            "models": [
                {
                    "id": entry.id,
                    "display_name": entry.display_name,
                    "deprecated": entry.deprecated,
                    "notes": entry.notes,
                    "supported_effort": entry.supported_effort,
                    "provider": entry.provider,
                    "provider_id": entry.provider_id,
                    "model": entry.model,
                    "source": entry.source,
                }
                for entry in catalog.models
            ],
        }

    def _runtime_probe_cache_path(self, engine: str) -> Path:
        cache_dir = Path(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_DIR)
        template = str(config.SYSTEM.ENGINE_MODELS_CATALOG_CACHE_FILE_TEMPLATE)
        return cache_dir / template.format(engine=engine)

    def _normalize_snapshot_models(self, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not models:
            raise ValueError("models must not be empty")
        normalized: List[Dict[str, Any]] = []
        seen_ids = set()
        for entry in models:
            model_id = entry.get("id")
            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError("model.id must be a non-empty string")
            model_id = model_id.strip()
            if model_id in seen_ids:
                raise ValueError(f"Duplicate model id: {model_id}")
            seen_ids.add(model_id)

            display_name = entry.get("display_name")
            if display_name is not None and not isinstance(display_name, str):
                raise ValueError("model.display_name must be a string or null")

            deprecated = entry.get("deprecated", False)
            if not isinstance(deprecated, bool):
                raise ValueError("model.deprecated must be a boolean")

            notes = entry.get("notes")
            if notes is not None and not isinstance(notes, str):
                raise ValueError("model.notes must be a string or null")

            supported_effort = entry.get("supported_effort")
            if supported_effort is not None:
                if not isinstance(supported_effort, list) or not all(
                    isinstance(item, str) and item for item in supported_effort
                ):
                    raise ValueError("model.supported_effort must be a list of non-empty strings")

            normalized_entry: Dict[str, Any] = {
                "id": model_id,
                "display_name": display_name,
                "deprecated": deprecated,
                "notes": notes,
            }
            if supported_effort is not None:
                normalized_entry["supported_effort"] = supported_effort
            provider = entry.get("provider")
            if provider is not None:
                if not isinstance(provider, str) or not provider.strip():
                    raise ValueError("model.provider must be a non-empty string or null")
                normalized_entry["provider"] = provider.strip()
            provider_id = entry.get("provider_id")
            if provider_id is not None:
                if not isinstance(provider_id, str) or not provider_id.strip():
                    raise ValueError("model.provider_id must be a non-empty string or null")
                normalized_entry["provider_id"] = provider_id.strip()
            model_name = entry.get("model")
            if model_name is not None:
                if not isinstance(model_name, str) or not model_name.strip():
                    raise ValueError("model.model must be a non-empty string or null")
                normalized_entry["model"] = model_name.strip()
            normalized.append(normalized_entry)
        return normalized

    def _select_snapshot_version(
        self,
        cli_version: Optional[str],
        snapshot_versions: List[str]
    ) -> Tuple[str, Optional[str]]:
        if not snapshot_versions:
            raise ValueError("No model snapshots available")

        parsed_cli = self._parse_semver(cli_version) if cli_version else None
        candidates: List[str] = []
        if parsed_cli:
            for ver in snapshot_versions:
                parsed = self._parse_semver(ver)
                if parsed and parsed <= parsed_cli:
                    candidates.append(ver)
            if candidates:
                return max(candidates, key=self._semver_key), None
            return max(snapshot_versions, key=self._semver_key), "no_match"

        fallback_reason = "cli_version_unknown" if cli_version is None else "no_semver_match"
        return max(snapshot_versions, key=self._semver_key), fallback_reason

    def _parse_semver(self, version: Optional[str]) -> Optional[Tuple[int, ...]]:
        if not version:
            return None
        match = re.search(r"\d+(\.\d+)+", version)
        if not match:
            return None
        try:
            return tuple(int(part) for part in match.group(0).split("."))
        except ValueError:
            return None

    def _semver_key(self, version: str) -> Tuple[int, ...]:
        parsed = self._parse_semver(version)
        return parsed if parsed is not None else (0,)

    def is_multi_provider_engine(self, engine: str) -> bool:
        profile = self._adapter_profile(engine.strip().lower())
        return bool(profile.provider_contract.multi_provider)

    def canonical_provider_id(self, engine: str) -> str | None:
        profile = self._adapter_profile(engine.strip().lower())
        return profile.provider_contract.canonical_provider_id

    def _parse_model_selector(self, model_spec: str | None) -> Dict[str, Optional[str]]:
        raw = model_spec.strip() if isinstance(model_spec, str) else ""
        if not raw:
            return {"provider": None, "model": None, "effort": None}
        model_part = raw
        effort: Optional[str] = None
        if "@" in raw:
            model_part, effort_part = raw.rsplit("@", 1)
            if not model_part.strip() or not effort_part.strip():
                raise ValueError("Invalid model specification format")
            model_part = model_part.strip()
            effort = effort_part.strip().lower()
        provider, model_name = self._split_provider_model(model_part)
        if provider and model_name:
            return {"provider": provider, "model": model_name, "effort": effort}
        return {"provider": None, "model": model_part.strip(), "effort": effort}

    def _find_model(self, models: List[ModelEntry], model_id: str) -> Optional[ModelEntry]:
        for entry in models:
            if entry.id == model_id:
                return entry
        return None

    def _resolve_model_entry(
        self,
        *,
        engine: str,
        models: List[ModelEntry],
        model: str,
        provider_id: str | None,
    ) -> Optional[ModelEntry]:
        profile = self._adapter_profile(engine)
        if not profile.provider_contract.multi_provider:
            for entry in models:
                candidates = {entry.id, self._model_value_for_entry(entry)}
                if model in candidates:
                    return entry
            return None
        if provider_id is None:
            return None
        for entry in models:
            entry_provider = self._normalize_provider_id(entry.provider_id or entry.provider)
            if entry_provider != provider_id:
                continue
            if model in {entry.id, self._model_value_for_entry(entry)}:
                return entry
        return None

    def _normalize_provider_id(self, provider_id: str | None) -> str | None:
        if not isinstance(provider_id, str):
            return None
        normalized = provider_id.strip().lower()
        return normalized or None

    def _normalize_effort(self, effort: str | None) -> str:
        if not isinstance(effort, str) or not effort.strip():
            return "default"
        return effort.strip().lower()

    def _normalize_supported_effort(self, supported_effort: Optional[List[str]]) -> List[str]:
        if not supported_effort:
            return ["default"]
        normalized: List[str] = []
        for item in supported_effort:
            if not isinstance(item, str):
                continue
            text = item.strip().lower()
            if text and text not in normalized:
                normalized.append(text)
        return normalized or ["default"]

    def _resolve_effective_effort(self, *, requested_effort: str, supported_effort: List[str]) -> str | None:
        normalized_supported = self._normalize_supported_effort(supported_effort)
        if normalized_supported == ["default"]:
            return None
        if requested_effort == "default":
            if "medium" in normalized_supported:
                return "medium"
            return normalized_supported[0]
        if requested_effort not in normalized_supported:
            raise ValueError(
                f"Reasoning effort '{requested_effort}' not supported for selected model"
            )
        return requested_effort

    def _model_value_for_entry(self, entry: ModelEntry) -> str:
        if isinstance(entry.model, str) and entry.model.strip():
            return entry.model.strip()
        _provider, parsed_model = self._split_provider_model(entry.id)
        return parsed_model or entry.id

    def _split_provider_model(self, value: str | None) -> Tuple[str | None, str | None]:
        if not isinstance(value, str) or "/" not in value:
            return None, None
        provider, model = value.split("/", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if not provider or not model:
            return None, None
        return provider, model

    def _effective_provider_for_entry(
        self,
        *,
        engine: str,
        entry: ModelEntry,
        requested_provider_id: str | None,
    ) -> str | None:
        profile = self._adapter_profile(engine)
        if not profile.provider_contract.multi_provider:
            return profile.provider_contract.canonical_provider_id
        return self._normalize_provider_id(entry.provider_id or entry.provider or requested_provider_id)

    def _runtime_model_for_entry(
        self,
        *,
        engine: str,
        entry: ModelEntry,
        provider_id: str | None,
        model: str,
    ) -> str | None:
        if engine == "opencode":
            return entry.id
        if engine == "claude" and entry.source == "custom_provider" and provider_id:
            return f"{provider_id}/{model}"
        return model


model_registry = ModelRegistry()
