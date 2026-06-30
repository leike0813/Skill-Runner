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


_PRESET_PROVIDERS: dict[str, dict[str, Any]] = {
    "token-plan": {
        "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "env_key": "BAILIAN_TOKEN_PLAN_API_KEY",
        "name_prefix": "ModelStudio Token Plan",
        "models": [
            {"id": "qwen3.7-plus", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "qwen3.6-plus", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "qwen3.7-max", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "qwen3.6-flash", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "deepseek-v4-pro", "contextWindowSize": 1000000},
            {"id": "deepseek-v4-flash", "contextWindowSize": 1000000},
            {"id": "deepseek-v3.2", "contextWindowSize": 131072},
            {"id": "kimi-k2.7-code", "contextWindowSize": 262144, "enableThinking": True},
            {"id": "kimi-k2.6", "contextWindowSize": 262144, "enableThinking": True},
            {"id": "kimi-k2.5", "contextWindowSize": 262144, "enableThinking": True},
            {"id": "glm-5.2", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "glm-5.1", "contextWindowSize": 202752, "enableThinking": True},
            {"id": "glm-5", "contextWindowSize": 202752, "enableThinking": True},
            {"id": "MiniMax-M2.5", "contextWindowSize": 196608},
        ],
    },
    "alibaba-standard": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "name_prefix": "ModelStudio Standard",
        "models": [
            {"id": "qwen3.6-plus", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "qwen3.7-plus", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "qwen3.7-max", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "glm-5.1", "contextWindowSize": 202752, "enableThinking": True},
            {"id": "deepseek-v4-pro", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "deepseek-v4-flash", "contextWindowSize": 1000000},
        ],
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
        "name_prefix": "DeepSeek",
        "models": [
            {"id": "deepseek-v4-pro", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "deepseek-v4-flash", "contextWindowSize": 1000000},
        ],
    },
    "minimax": {
        "base_url": "https://api.minimax.io/v1",
        "env_key": "MINIMAX_API_KEY",
        "name_prefix": "MiniMax",
        "models": [
            {"id": "MiniMax-M3", "contextWindowSize": 1000000},
            {"id": "MiniMax-M2.7", "contextWindowSize": 204800},
            {"id": "MiniMax-M2.7-highspeed", "contextWindowSize": 204800},
            {"id": "MiniMax-M2.5", "contextWindowSize": 196608},
            {"id": "MiniMax-M2.5-highspeed", "contextWindowSize": 196608},
        ],
    },
    "zai": {
        "base_url": "https://api.z.ai/api/paas/v4",
        "env_key": "ZAI_API_KEY",
        "name_prefix": "Z.AI",
        "models": [
            {"id": "GLM-5.2", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "GLM-5.1", "contextWindowSize": 204800, "enableThinking": True},
            {"id": "GLM-5", "contextWindowSize": 204800},
            {"id": "GLM-5-Turbo", "contextWindowSize": 204800},
        ],
    },
    "idealab": {
        "base_url": "https://idealab.alibaba-inc.com/api/openai/v1",
        "env_key": "IDEALAB_API_KEY",
        "name_prefix": "Idealab",
        "models": [
            {"id": "Qwen3.6-Plus-DogFooding", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "bailian/deepseek-v4-pro", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "bailian/deepseek-v4-flash", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "bailian/kimi-k2.6", "contextWindowSize": 262144, "enableThinking": True},
        ],
    },
    "modelscope": {
        "base_url": "https://api-inference.modelscope.cn/v1",
        "env_key": "MODELSCOPE_API_KEY",
        "name_prefix": "ModelScope",
        "models": [
            {"id": "deepseek-ai/DeepSeek-V4-Flash", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "Qwen/Qwen3.5-397B-A17B", "contextWindowSize": 1000000, "enableThinking": True},
            {"id": "ZhipuAI/GLM-5.1", "contextWindowSize": 1000000, "enableThinking": True},
        ],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "name_prefix": "OpenRouter",
        "models": [
            {"id": "z-ai/glm-4.5-air:free", "contextWindowSize": 128000},
            {"id": "openai/gpt-oss-120b:free", "contextWindowSize": 131072},
        ],
    },
    "requesty": {
        "base_url": "https://router.requesty.ai/v1",
        "env_key": "REQUESTY_API_KEY",
        "name_prefix": "Requesty",
        "models": [
            {"id": "openai/gpt-4o-mini", "contextWindowSize": 128000},
            {"id": "openai/gpt-4o", "contextWindowSize": 128000},
        ],
    },
}

_MANAGED_ENV_KEYS = {
    "BAILIAN_CODING_PLAN_API_KEY",
    *(str(preset["env_key"]) for preset in _PRESET_PROVIDERS.values()),
}
_MANAGED_BASE_URLS = {
    "https://coding.dashscope.aliyuncs.com/v1",
    "https://coding-intl.dashscope.aliyuncs.com/v1",
    *(str(preset["base_url"]) for preset in _PRESET_PROVIDERS.values()),
}


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
        if region is None and provider_id not in _PRESET_PROVIDERS:
            raise ValueError(f"Unknown qwen API-key provider: {provider_id}")
        return CodingPlanSession(
            session_id=session_id,
            provider_id=provider_id,
            region=str(region["id"]) if region is not None else "",
        )

    def complete_api_key(self, runtime: CodingPlanSession, api_key: str) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("API key is required")
        model_providers = self._build_model_providers(runtime.provider_id)
        env_key = self._env_key_for_provider(runtime.provider_id)
        new_settings = {
            "modelProviders": {"openai": model_providers},
            "env": {env_key: normalized_key},
            "security": {"auth": {"selectedType": "openai"}},
            "model": {"name": model_providers[0]["id"]},
        }
        region = self.REGIONS.get(runtime.provider_id)
        if region is not None:
            new_settings["codingPlan"] = {"region": region["id"]}

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
                unmanaged_rows = [
                    row for row in existing_rows if not self._is_managed_model_provider(row)
                ]
                merged["modelProviders"][provider_type] = list(providers) + unmanaged_rows

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

    def _is_managed_model_provider(self, row: Any) -> bool:
        if not isinstance(row, dict):
            return False
        base_url = str(row.get("baseUrl") or "").strip().lower()
        env_key = str(row.get("envKey") or "").strip()
        return env_key in _MANAGED_ENV_KEYS or base_url in _MANAGED_BASE_URLS

    def _build_model_providers(self, provider_id: str) -> list[dict[str, Any]]:
        region = self.REGIONS.get(provider_id)
        if region is None:
            return self._build_preset_model_providers(provider_id)
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

    def _build_preset_model_providers(self, provider_id: str) -> list[dict[str, Any]]:
        preset = _PRESET_PROVIDERS.get(provider_id)
        if preset is None:
            raise ValueError(f"Unknown qwen API-key provider: {provider_id}")
        env_key = str(preset["env_key"])
        base_url = str(preset["base_url"])
        name_prefix = str(preset["name_prefix"])
        providers: list[dict[str, Any]] = []
        for row in preset["models"]:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if not model_id:
                continue
            provider_payload: dict[str, Any] = {
                "id": model_id,
                "name": f"{name_prefix} {model_id}",
                "baseUrl": base_url,
                "envKey": env_key,
            }
            generation_config: dict[str, Any] = {}
            context_window_size = row.get("contextWindowSize")
            if isinstance(context_window_size, int):
                generation_config["contextWindowSize"] = context_window_size
            if row.get("enableThinking") is True:
                generation_config["extra_body"] = {"enable_thinking": True}
            if generation_config:
                provider_payload["generationConfig"] = generation_config
            providers.append(provider_payload)
        if not providers:
            raise RuntimeError(f"No usable qwen preset models found for provider {provider_id}")
        return providers

    def _env_key_for_provider(self, provider_id: str) -> str:
        if provider_id in self.REGIONS:
            return "BAILIAN_CODING_PLAN_API_KEY"
        preset = _PRESET_PROVIDERS.get(provider_id)
        if preset is None:
            raise ValueError(f"Unknown qwen API-key provider: {provider_id}")
        return str(preset["env_key"])

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
