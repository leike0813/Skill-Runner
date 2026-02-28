from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from server.services.config_generator import config_generator
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import GeminiExecutionAdapter

logger = logging.getLogger(__name__)


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
                    engine_defaults = json.load(f)
            except Exception:
                logger.exception("Failed to load Gemini engine defaults")

        skill_defaults: dict[str, object] = {}
        gemini_settings_file = self._adapter.profile.resolve_skill_defaults_path(skill.path)
        if gemini_settings_file is not None:
            if gemini_settings_file.exists():
                try:
                    with open(gemini_settings_file, "r", encoding="utf-8") as f:
                        skill_defaults = json.load(f)
                    logger.info("Loaded skill defaults from %s", gemini_settings_file)
                except Exception:
                    logger.exception("Failed to load skill defaults")

        user_overrides: dict[str, object] = {}
        if "model" in options:
            user_overrides.setdefault("model", {})["name"] = options["model"]  # type: ignore[index]
        if "temperature" in options:
            user_overrides.setdefault("model", {})["temperature"] = float(options["temperature"])  # type: ignore[index]
        if "max_tokens" in options:
            user_overrides.setdefault("model", {})["maxOutputTokens"] = int(options["max_tokens"])  # type: ignore[index]

        runtime_engine_overrides: dict[str, object] = {}
        if isinstance(options.get("gemini_config"), dict):
            runtime_engine_overrides = options["gemini_config"]

        enforced_config_path = self._adapter.profile.resolve_enforced_config_path()
        project_enforced: dict[str, object] = {}
        if enforced_config_path.exists():
            try:
                with open(enforced_config_path, "r", encoding="utf-8") as f:
                    project_enforced = json.load(f)
            except Exception:
                logger.exception("Failed to load project enforced config")

        layers = [engine_defaults, skill_defaults, user_overrides, runtime_engine_overrides, project_enforced]
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path = self._adapter.profile.resolve_settings_schema_path()
        if schema_path is None:
            raise RuntimeError("Gemini adapter profile missing settings schema path")
        config_generator.generate_config(schema_path.name, layers, settings_path)
        return settings_path
