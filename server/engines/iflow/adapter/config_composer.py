from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from server.engines.common.config.json_layer_config_generator import config_generator
from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import IFlowExecutionAdapter

logger = logging.getLogger(__name__)

_JSON_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)
_COMPOSE_CONFIG_EXCEPTIONS = (
    FileNotFoundError,
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
    AttributeError,
    RuntimeError,
)


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
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    raise ValueError("iFlow engine defaults must be a JSON object")
                engine_defaults = payload
            except _JSON_LOAD_EXCEPTIONS:
                logger.exception("Failed to load iFlow engine defaults")

        skill_defaults: dict[str, object] = {}
        skill_settings_path = self._adapter.profile.resolve_skill_defaults_path(skill.path)
        if skill_settings_path is not None:
            if skill_settings_path.exists():
                try:
                    with open(skill_settings_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    if not isinstance(payload, dict):
                        raise ValueError("iFlow skill defaults must be a JSON object")
                    skill_defaults = payload
                    logger.info("Loaded skill defaults from %s", skill_settings_path)
                except _JSON_LOAD_EXCEPTIONS:
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
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    raise ValueError("iFlow enforced config must be a JSON object")
                enforced_config = payload
            except _JSON_LOAD_EXCEPTIONS:
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
        except _COMPOSE_CONFIG_EXCEPTIONS as exc:
            raise RuntimeError(f"Failed to generate iFlow configuration: {exc}") from exc
