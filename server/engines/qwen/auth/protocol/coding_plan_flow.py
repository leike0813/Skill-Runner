from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.services.engine_management.model_registry import model_registry

@dataclass
class CodingPlanSession:
    session_id: str
    provider_id: str
    region: str


class CodingPlanAuthFlow:
    """
    API-key driven Qwen Coding Plan auth flow used by oauth_proxy sessions.
    """

    REGIONS = {
        "coding-plan-china": {
            "id": "china",
            "name": "China (cn-beijing)",
            "endpoint": "https://coding.dashscope.aliyuncs.com/v1",
        },
        "coding-plan-global": {
            "id": "global",
            "name": "Global (intl)",
            "endpoint": "https://coding-intl.dashscope.aliyuncs.com/v1",
        },
    }

    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    def _qwen_config_dir(self) -> Path:
        return self.agent_home / ".qwen"

    def _settings_path(self) -> Path:
        return self._qwen_config_dir() / "settings.json"

    def start_session(self, *, session_id: str, provider_id: str) -> CodingPlanSession:
        region = self.REGIONS.get(provider_id)
        if region is None:
            raise ValueError(f"Unknown coding-plan provider: {provider_id}")
        return CodingPlanSession(
            session_id=session_id,
            provider_id=provider_id,
            region=str(region["id"]),
        )

    def complete_api_key(self, runtime: CodingPlanSession, api_key: str) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("API key is required")
        region = self.REGIONS.get(runtime.provider_id)
        if region is None:
            raise RuntimeError(f"Unknown provider: {runtime.provider_id}")

        model_providers = self._build_model_providers(runtime.provider_id)
        new_settings = {
            "modelProviders": {"openai": model_providers},
            "env": {"BAILIAN_CODING_PLAN_API_KEY": normalized_key},
            "security": {"auth": {"selectedType": "openai"}},
            "codingPlan": {"region": region["id"]},
            "model": {"name": model_providers[0]["id"]},
        }

        settings_path = self._settings_path()
        if settings_path.exists():
            try:
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}
        else:
            existing = {}

        merged = self._merge_settings(existing, new_settings)
        config_dir = self._qwen_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _merge_settings(
        self,
        existing: dict[str, Any],
        new: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(existing)

        if "modelProviders" in new:
            if "modelProviders" not in merged:
                merged["modelProviders"] = {}

            for provider_type, providers in new["modelProviders"].items():
                existing_rows = merged["modelProviders"].get(provider_type, [])
                if not isinstance(existing_rows, list):
                    existing_rows = []
                non_coding_plan_rows = [
                    row for row in existing_rows if not self._is_coding_plan_model_provider(row)
                ]
                merged["modelProviders"][provider_type] = list(providers) + non_coding_plan_rows

        if "env" in new:
            if "env" not in merged:
                merged["env"] = {}
            merged["env"].update(new["env"])

        if "security" in new:
            if "security" not in merged:
                merged["security"] = {}
            if "auth" in new["security"]:
                merged["security"]["auth"] = new["security"]["auth"]

        if "codingPlan" in new:
            merged["codingPlan"] = new["codingPlan"]

        if "model" in new:
            merged["model"] = new["model"]

        return merged

    def _is_coding_plan_model_provider(self, row: Any) -> bool:
        if not isinstance(row, dict):
            return False
        base_url = str(row.get("baseUrl") or "").strip().lower()
        env_key = str(row.get("envKey") or "").strip()
        return env_key == "BAILIAN_CODING_PLAN_API_KEY" or "coding.dashscope.aliyuncs.com" in base_url or "coding-intl.dashscope.aliyuncs.com" in base_url

    def _build_model_providers(self, provider_id: str) -> list[dict[str, Any]]:
        region = self.REGIONS.get(provider_id)
        if region is None:
            raise ValueError(f"Unknown coding-plan provider: {provider_id}")
        snapshot_models = self._load_snapshot_models(provider_id)
        if not snapshot_models:
            raise RuntimeError(f"No qwen snapshot models found for provider {provider_id}")
        providers: list[dict[str, Any]] = []
        for entry in snapshot_models:
            model_id = str(entry.get("model") or entry.get("id") or "").strip()
            if not model_id:
                continue
            provider_payload: dict[str, Any] = {
                "id": model_id,
                "name": str(entry.get("settings_name") or entry.get("display_name") or model_id),
                "baseUrl": str(entry.get("settings_base_url") or region["endpoint"]),
                "envKey": "BAILIAN_CODING_PLAN_API_KEY",
            }
            generation_config = entry.get("generation_config") or entry.get("generationConfig")
            if isinstance(generation_config, dict) and generation_config:
                provider_payload["generationConfig"] = generation_config
            providers.append(provider_payload)
        if not providers:
            raise RuntimeError(f"No usable qwen Coding Plan models found for provider {provider_id}")
        return providers

    def _load_snapshot_models(self, provider_id: str) -> list[dict[str, Any]]:
        catalog = model_registry.get_models("qwen", refresh=True)
        snapshot_version = catalog.snapshot_version_used
        if not isinstance(snapshot_version, str) or not snapshot_version.strip():
            raise RuntimeError("Unable to resolve qwen model snapshot version")
        manifest = model_registry._load_manifest("qwen")  # noqa: SLF001
        snapshot_file = model_registry._snapshot_file(manifest, snapshot_version)  # noqa: SLF001
        payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
        models = payload.get("models", [])
        if not isinstance(models, list):
            return []
        return [
            entry
            for entry in models
            if isinstance(entry, dict) and str(entry.get("provider_id") or "").strip().lower() == provider_id
        ]
