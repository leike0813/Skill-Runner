from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from server.services.codex_config_manager import CodexConfigManager

from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import CodexExecutionAdapter

logger = logging.getLogger(__name__)

RUNNER_ONLY_OPTION_KEYS = {
    "verbose",
    "no_cache",
    "debug",
    "debug_keep_temp",
    "execution_mode",
    "interactive_require_user_reply",
    "session_timeout_sec",
    "interactive_wait_timeout_sec",
    "hard_wait_timeout_sec",
    "wait_timeout_sec",
    "hard_timeout_seconds",
}

CODEX_CONFIG_PASSTHROUGH_KEYS = {
    "model",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "model_supports_reasoning_summaries",
}


class CodexConfigComposer:
    def __init__(self, adapter: "CodexExecutionAdapter") -> None:
        self._adapter = adapter

    def extract_codex_overrides(self, options: dict[str, Any]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}

        raw_codex_config = options.get("codex_config")
        if isinstance(raw_codex_config, dict):
            for key, value in raw_codex_config.items():
                if not isinstance(key, str):
                    continue
                if key.startswith("__"):
                    continue
                if key in RUNNER_ONLY_OPTION_KEYS:
                    continue
                overrides[key] = value

        for key in CODEX_CONFIG_PASSTHROUGH_KEYS:
            if key not in options:
                continue
            value = options.get(key)
            if value is None:
                continue
            overrides[key] = value

        return overrides

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        options = ctx.options
        skill_defaults: dict[str, Any] = {}
        if skill.path:
            settings_path = self._adapter.profile.resolve_skill_defaults_path(skill.path)
            if settings_path is not None and settings_path.exists():
                try:
                    import tomlkit

                    with open(settings_path, "r", encoding="utf-8") as f:
                        skill_defaults = tomlkit.parse(f.read())
                    logger.info("Loaded skill defaults from %s", settings_path)
                except Exception as exc:
                    logger.warning("Failed to load skill settings: %s", exc)

        try:
            profile_name_override = options.get("__codex_profile_name")
            profile_name = (
                profile_name_override.strip()
                if isinstance(profile_name_override, str)
                else ""
            )
            config_manager = self._adapter.config_manager
            if profile_name:
                if isinstance(self._adapter.config_manager, CodexConfigManager):
                    config_manager = CodexConfigManager(
                        config_path=self._adapter.config_manager.config_path,
                        profile_name=profile_name,
                        default_config_path=self._adapter.config_manager.DEFAULT_CONFIG_PATH,
                        enforced_config_path=self._adapter.config_manager.ENFORCED_CONFIG_PATH,
                        schema_path=self._adapter.config_manager.SCHEMA_PATH,
                    )
                else:
                    try:
                        setattr(config_manager, "profile_name", profile_name)
                    except Exception:
                        pass
            codex_overrides = self.extract_codex_overrides(options)
            fused_settings = config_manager.generate_profile_settings(skill_defaults, codex_overrides)
            active_profile_name = getattr(
                config_manager,
                "profile_name",
                CodexConfigManager.PROFILE_NAME,
            )
            logger.info("Updating Codex profile '%s' with fused settings", active_profile_name)
            config_manager.update_profile(fused_settings)
            return config_manager.config_path
        except ValueError as exc:
            raise RuntimeError(f"Configuration Error: {exc}")
