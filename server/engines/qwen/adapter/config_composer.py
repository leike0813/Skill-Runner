from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.mcp import build_mcp_config_layer, validate_no_mcp_root_keys
from server.services.skill.skill_asset_resolver import (
    load_resolved_json,
    resolve_engine_config_asset,
)

if TYPE_CHECKING:
    from .execution_adapter import QwenExecutionAdapter

logger = logging.getLogger(__name__)

RUNNER_ONLY_OPTION_KEYS = {
    "no_cache",
    "execution_mode",
    "interactive_auto_reply",
    "interactive_reply_timeout_sec",
    "hard_timeout_seconds",
}


class QwenConfigComposer:
    """
    Configuration composer for Qwen Code.

    Composes configuration from:
    1. Skill defaults (from runner.json.engine_configs.qwen or fallback)
    2. Runtime overrides (from request options)
    3. Enforced configuration (from enforced.json)
    """

    def __init__(self, adapter: "QwenExecutionAdapter") -> None:
        self._adapter = adapter

    def _load_json_config(self, config_path: Path, *, label: str) -> dict[str, Any]:
        if not config_path.exists():
            return {}
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            logger.warning("Failed to load %s config: %s", label, config_path, exc_info=True)
            return {}
        return payload if isinstance(payload, dict) else {}

    def _deep_merge_dicts(self, base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge_dicts(base[key], value)
            else:
                base[key] = value
        return base

    def _model_overlay(self, options: dict[str, Any]) -> dict[str, Any]:
        model_obj = options.get("runtime_model")
        if not isinstance(model_obj, str) or not model_obj.strip():
            model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            return {"model": {"name": model_obj.strip()}}
        return {}

    def extract_qwen_overrides(self, options: dict[str, Any]) -> dict[str, Any]:
        """
        Extract Qwen-specific configuration overrides from options.

        Args:
            options: Runtime options from the request

        Returns:
            Dictionary of Qwen-specific overrides
        """
        overrides: dict[str, Any] = {}

        raw_qwen_config = options.get("qwen_config")
        if isinstance(raw_qwen_config, dict):
            for key, value in raw_qwen_config.items():
                if not isinstance(key, str):
                    continue
                if key.startswith("__"):
                    continue
                if key in RUNNER_ONLY_OPTION_KEYS:
                    continue
                overrides[key] = value

        return overrides

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        """
        Compose and write Qwen configuration.

        Args:
            ctx: Execution context containing skill and options

        Returns:
            Path to the composed configuration file
        """
        skill = ctx.skill
        options = ctx.options

        layers: list[dict[str, Any]] = []
        layers.append(
            self._load_json_config(
                self._adapter.profile.resolve_default_config_path(),
                label="qwen default",
            )
        )

        skill_defaults: dict[str, Any] = {}
        if skill.path:
            settings_resolution = resolve_engine_config_asset(
                skill,
                "qwen",
                self._adapter.profile.config_assets.skill_defaults_path,
            )
            if settings_resolution.used_fallback and settings_resolution.issue_source == "declared":
                logger.warning(
                    "Qwen skill config declaration fallback: skill=%s declared=%s fallback=%s issue=%s",
                    skill.id,
                    settings_resolution.declared_relpath,
                    settings_resolution.fallback_relpath,
                    settings_resolution.issue_code,
                )
            payload = load_resolved_json(settings_resolution.path)
            if payload is not None:
                skill_defaults = payload
        validate_no_mcp_root_keys(skill_defaults, source="Qwen skill config")
        layers.append(skill_defaults)
        runtime_overrides = self.extract_qwen_overrides(options)
        validate_no_mcp_root_keys(runtime_overrides, source="Qwen runtime override")
        layers.append(runtime_overrides)
        layers.append(self._model_overlay(options))
        _, governed_mcp = build_mcp_config_layer(skill=skill, engine="qwen")
        layers.append(governed_mcp)
        layers.append(
            self._load_json_config(
                self._adapter.profile.resolve_enforced_config_path(),
                label="qwen enforced",
            )
        )

        fused_settings: dict[str, Any] = {}
        for layer in layers:
            if isinstance(layer, dict):
                self._deep_merge_dicts(fused_settings, layer)

        config_path = self._write_config(fused_settings, ctx.run_dir)

        logger.info("Composed Qwen configuration at %s", config_path)

        return config_path

    def _write_config(
        self,
        config: dict[str, Any],
        run_dir: Path,
    ) -> Path:
        """
        Write configuration to run directory.

        Args:
            config: Configuration dictionary to write
            run_dir: Run directory path

        Returns:
            Path to the written configuration file
        """
        qwen_dir = run_dir / ".qwen"
        qwen_dir.mkdir(parents=True, exist_ok=True)

        config_path = qwen_dir / "settings.json"

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")

        return config_path
