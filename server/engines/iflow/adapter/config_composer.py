from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from server.services.config_generator import config_generator
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import IFlowExecutionAdapter

logger = logging.getLogger(__name__)


class IFlowConfigComposer:
    def __init__(self, adapter: "IFlowExecutionAdapter") -> None:
        self._adapter = adapter

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        run_dir = ctx.run_dir
        options = ctx.options

        engine_defaults: dict[str, object] = {}
        default_config_path = self._adapter.profile.resolve_default_config_path()
        if default_config_path.exists():
            try:
                with open(default_config_path, "r", encoding="utf-8") as f:
                    engine_defaults = json.load(f)
            except Exception:
                logger.exception("Failed to load iFlow engine defaults")

        skill_defaults: dict[str, object] = {}
        skill_settings_path = self._adapter.profile.resolve_skill_defaults_path(skill.path)
        if skill_settings_path is not None:
            if skill_settings_path.exists():
                try:
                    with open(skill_settings_path, "r", encoding="utf-8") as f:
                        skill_defaults = json.load(f)
                    logger.info("Loaded skill defaults from %s", skill_settings_path)
                except Exception:
                    logger.exception("Failed to load skill defaults")

        user_overrides: dict[str, object] = {}
        if "model" in options:
            user_overrides["modelName"] = options["model"]

        runtime_engine_overrides: dict[str, object] = {}
        if isinstance(options.get("iflow_config"), dict):
            runtime_engine_overrides = options["iflow_config"]

        enforced_config: dict[str, object] = {}
        enforced_path = self._adapter.profile.resolve_enforced_config_path()
        if enforced_path.exists():
            try:
                with open(enforced_path, "r", encoding="utf-8") as f:
                    enforced_config = json.load(f)
            except Exception:
                logger.exception("Failed to load iFlow enforced config")

        layers = [engine_defaults, skill_defaults, user_overrides, runtime_engine_overrides, enforced_config]
        target_path = run_dir / ".iflow" / "settings.json"
        try:
            schema_path = self._adapter.profile.resolve_settings_schema_path()
            if schema_path is None:
                raise RuntimeError("iFlow adapter profile missing settings schema path")
            config_generator.generate_config(
                schema_name=schema_path.name,
                config_layers=layers,
                output_path=target_path,
            )
            return target_path
        except Exception as exc:
            raise RuntimeError(f"Failed to generate iFlow configuration: {exc}") from exc
