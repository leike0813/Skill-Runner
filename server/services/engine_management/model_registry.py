import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        catalog = self.get_models(engine)
        model_name, effort = self._parse_model_spec(engine, model_spec)
        model_entry = self._find_model(catalog.models, model_name)
        if not model_entry and self._is_claude_custom_model_spec(engine, model_name):
            model_entry = ModelEntry(
                id=model_name,
                display_name=model_name,
                deprecated=False,
                notes=None,
                supported_effort=None,
                provider=self._provider_from_model_spec(model_name),
                model=self._model_name_from_model_spec(model_name),
                source="custom_provider",
            )
        if not model_entry:
            raise ValueError(f"Model '{model_name}' not allowed for engine '{engine}'")
        if effort:
            allowed = model_entry.supported_effort or self._default_effort_levels()
            if effort not in allowed:
                raise ValueError(f"Reasoning effort '{effort}' not supported for model '{model_name}'")
        payload = {"model": model_name}
        if effort:
            payload["model_reasoning_effort"] = effort
        return payload

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
        normalized = self._normalize_official_models(engine, models)
        return self._merge_custom_provider_models(engine, normalized)

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
                    model=entry.get("model"),
                    source=str(entry.get("source") or "official"),
                )
            )
        return models

    def _normalize_official_models(self, engine: str, models: List[ModelEntry]) -> List[ModelEntry]:
        if engine != "claude":
            return [
                ModelEntry(
                    id=item.id,
                    display_name=item.display_name,
                    deprecated=item.deprecated,
                    notes=item.notes,
                    supported_effort=item.supported_effort,
                    provider=item.provider,
                    model=item.model,
                    source="official",
                )
                for item in models
            ]
        normalized: List[ModelEntry] = []
        for item in models:
            normalized.append(
                ModelEntry(
                    id=item.id,
                    display_name=item.display_name,
                    deprecated=item.deprecated,
                    notes=item.notes,
                    supported_effort=item.supported_effort,
                    provider=item.provider or "anthropic",
                    model=item.model or item.id,
                    source="official",
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
                        model=row.get("model"),
                        source=str(row.get("source") or "official"),
                    )
                )
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

    def _parse_model_spec(self, engine: str, model_spec: str) -> Tuple[str, Optional[str]]:
        if self._uses_runtime_probe_catalog(engine):
            if "@" in model_spec:
                raise ValueError(f"Engine '{engine}' does not support model reasoning suffix")
            if not re.fullmatch(r"[^/\s]+/[^/\s]+", model_spec):
                raise ValueError(
                    f"Engine '{engine}' requires model format '<provider>/<model>'"
                )
            return model_spec, None
        if engine == "claude":
            if "@" in model_spec:
                raise ValueError(f"Engine '{engine}' does not support model reasoning suffix")
            return model_spec, None
        if engine != "codex":
            if "@" in model_spec:
                raise ValueError(f"Engine '{engine}' does not support model reasoning suffix")
            return model_spec, None
        if "@" not in model_spec:
            return model_spec, None
        name, effort = model_spec.split("@", 1)
        if not name or not effort:
            raise ValueError("Invalid model specification format")
        return name, effort

    def _find_model(self, models: List[ModelEntry], model_id: str) -> Optional[ModelEntry]:
        for entry in models:
            if entry.id == model_id:
                return entry
        return None

    def _default_effort_levels(self) -> List[str]:
        return ["minimal", "low", "medium", "high", "xhigh"]

    def _is_claude_custom_model_spec(self, engine: str, model_spec: str) -> bool:
        if engine != "claude":
            return False
        return re.fullmatch(r"[^/\s]+/[^/\s]+", model_spec) is not None

    def _provider_from_model_spec(self, model_spec: str) -> str | None:
        if "/" not in model_spec:
            return None
        provider, _ = model_spec.split("/", 1)
        return provider or None

    def _model_name_from_model_spec(self, model_spec: str) -> str | None:
        if "/" not in model_spec:
            return None
        _provider, model = model_spec.split("/", 1)
        return model or None


model_registry = ModelRegistry()
