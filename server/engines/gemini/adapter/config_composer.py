from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from server.engines.common.config.json_layer_config_generator import config_generator
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.mcp import McpConfigError, build_mcp_config_layer, validate_no_mcp_root_keys
from server.services.skill.skill_asset_resolver import (
    load_resolved_json,
    resolve_engine_config_asset,
)

if TYPE_CHECKING:
    from .execution_adapter import GeminiExecutionAdapter

logger = logging.getLogger(__name__)

_JSON_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)


class GeminiConfigComposer:
    def __init__(self, adapter: "GeminiExecutionAdapter") -> None:
        self._adapter = adapter

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        run_dir = ctx.run_dir
        options = ctx.options

        gemini_config_dir = run_dir / ".gemini"
        settings_path = gemini_config_dir / "settings.json"

        engine_defaults: dict[str, object] = {}
        default_config_path = self._adapter.profile.resolve_default_config_path()
        if default_config_path.exists():
            try:
                with open(default_config_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    raise ValueError("Gemini engine defaults must be a JSON object")
                engine_defaults = payload
            except _JSON_LOAD_EXCEPTIONS:
                logger.exception("Failed to load Gemini engine defaults")

        skill_defaults: dict[str, object] = {}
        skill_config_resolution = resolve_engine_config_asset(
            skill,
            "gemini",
            self._adapter.profile.config_assets.skill_defaults_path,
        )
        if skill_config_resolution.used_fallback and skill_config_resolution.issue_source == "declared":
            logger.warning(
                "Gemini skill config declaration fallback: skill=%s declared=%s fallback=%s issue=%s",
                skill.id,
                skill_config_resolution.declared_relpath,
                skill_config_resolution.fallback_relpath,
                skill_config_resolution.issue_code,
            )
        payload = load_resolved_json(skill_config_resolution.path)
        if payload is not None:
            skill_defaults = payload
            logger.info("Loaded skill defaults from %s", skill_config_resolution.path)
        elif skill_config_resolution.path is not None:
            logger.warning("Failed to load Gemini skill defaults: %s", skill_config_resolution.path)
        validate_no_mcp_root_keys(skill_defaults, source="Gemini skill config")

        user_overrides: dict[str, object] = {}
        model_obj = options.get("runtime_model", options.get("model"))
        if model_obj is not None:
            user_overrides.setdefault("model", {})["name"] = model_obj  # type: ignore[index]
        if "temperature" in options:
            user_overrides.setdefault("model", {})["temperature"] = float(options["temperature"])  # type: ignore[index]
        if "max_tokens" in options:
            user_overrides.setdefault("model", {})["maxOutputTokens"] = int(options["max_tokens"])  # type: ignore[index]

        runtime_engine_overrides: dict[str, object] = {}
        if isinstance(options.get("gemini_config"), dict):
            runtime_engine_overrides = options["gemini_config"]
        validate_no_mcp_root_keys(runtime_engine_overrides, source="Gemini runtime override")

        try:
            _, governed_mcp = build_mcp_config_layer(skill=skill, engine="gemini")
        except McpConfigError as exc:
            raise RuntimeError(f"Configuration Error: {exc}") from exc

        enforced_config_path = self._adapter.profile.resolve_enforced_config_path()
        project_enforced: dict[str, object] = {}
        if enforced_config_path.exists():
            try:
                with open(enforced_config_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    raise ValueError("Gemini enforced config must be a JSON object")
                project_enforced = payload
            except _JSON_LOAD_EXCEPTIONS:
                logger.exception("Failed to load project enforced config")

        layers = [
            engine_defaults,
            skill_defaults,
            user_overrides,
            runtime_engine_overrides,
            governed_mcp,
            project_enforced,
        ]
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path = self._adapter.profile.resolve_settings_schema_path()
        if schema_path is None:
            raise RuntimeError("Gemini adapter profile missing settings schema path")
        config_generator.generate_config(schema_path.name, layers, settings_path)
        return settings_path
