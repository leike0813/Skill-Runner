from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from server.config import config
from server.engines.common.config.json_layer_config_generator import config_generator
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.engine_management.engine_custom_provider_service import (
    engine_custom_provider_service,
)
from server.services.skill.skill_asset_resolver import load_resolved_json, resolve_engine_config_asset
from .sandbox_probe import load_claude_sandbox_probe

if TYPE_CHECKING:
    from .execution_adapter import ClaudeExecutionAdapter

logger = logging.getLogger(__name__)

_JSON_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)


def build_claude_model_env_overrides(model_spec: str) -> dict[str, object]:
    normalized_model = model_spec.strip()
    env_overrides: dict[str, object] = {"ANTHROPIC_MODEL": normalized_model}
    resolved_custom = engine_custom_provider_service.resolve_model("claude", normalized_model)
    if resolved_custom is not None:
        env_overrides = {
            "ANTHROPIC_AUTH_TOKEN": resolved_custom.api_key,
            "ANTHROPIC_BASE_URL": resolved_custom.base_url,
            "ANTHROPIC_MODEL": resolved_custom.model,
        }
    return env_overrides


class ClaudeConfigComposer:
    _SANDBOX_LIST_FIELDS: tuple[tuple[str, ...], ...] = (
        ("excludedCommands",),
        ("filesystem", "allowWrite"),
        ("filesystem", "denyWrite"),
        ("filesystem", "denyRead"),
        ("network", "allowedDomains"),
        ("network", "allowUnixSockets"),
    )

    def __init__(self, adapter: "ClaudeExecutionAdapter") -> None:
        self._adapter = adapter

    @staticmethod
    def _absolute_path_token(path: Path) -> str:
        return f"//{path.resolve()}"

    def _build_dynamic_enforced_config(self, *, run_dir: Path) -> dict[str, object]:
        agent_home = self._adapter.agent_manager.profile.agent_home.resolve()
        run_root = run_dir.resolve()
        dynamic_sandbox: dict[str, object] = {
            "filesystem": {
                "allowWrite": [self._absolute_path_token(run_root)],
                "denyWrite": [self._absolute_path_token(agent_home)],
            }
        }

        root_path = Path(config.SYSTEM.ROOT).resolve()
        if root_path != run_root and root_path != agent_home and root_path not in run_root.parents:
            dynamic_sandbox["filesystem"]["denyWrite"].append(self._absolute_path_token(root_path))  # type: ignore[index]

        return {"sandbox": dynamic_sandbox}

    @staticmethod
    def _get_nested_value(payload: dict[str, object], path: tuple[str, ...]) -> object | None:
        current: object = payload
        for token in path:
            if not isinstance(current, dict):
                return None
            current = current.get(token)
        return current

    @staticmethod
    def _set_nested_list(payload: dict[str, object], path: tuple[str, ...], values: list[str]) -> None:
        current: dict[str, object] = payload
        for token in path[:-1]:
            child = current.get(token)
            if not isinstance(child, dict):
                child = {}
                current[token] = child
            current = child
        current[path[-1]] = values

    @classmethod
    def _collect_sandbox_lists(
        cls,
        payload: dict[str, object],
    ) -> dict[tuple[str, ...], list[str]]:
        sandbox_obj = payload.get("sandbox")
        if not isinstance(sandbox_obj, dict):
            return {}
        collected: dict[tuple[str, ...], list[str]] = {}
        sandbox_payload: dict[str, object] = {"sandbox": sandbox_obj}
        for relative_path in cls._SANDBOX_LIST_FIELDS:
            full_path = ("sandbox", *relative_path)
            value = cls._get_nested_value(sandbox_payload, full_path)
            if not isinstance(value, list):
                continue
            normalized = [item for item in value if isinstance(item, str) and item.strip()]
            if normalized:
                collected[relative_path] = normalized
        return collected

    @staticmethod
    def _merge_unique_strings(existing: list[str], incoming: list[str]) -> list[str]:
        merged: list[str] = []
        for item in [*existing, *incoming]:
            if item not in merged:
                merged.append(item)
        return merged

    def _compose_layers(self, layers: list[dict[str, object]]) -> dict[str, object]:
        composed: dict[str, object] = {}
        for layer in layers:
            layer_copy = copy.deepcopy(layer)
            previous_sandbox_lists = self._collect_sandbox_lists(composed)
            current_sandbox_lists = self._collect_sandbox_lists(layer_copy)
            composed = config_generator.deep_merge(composed, layer_copy)
            if not current_sandbox_lists:
                continue
            sandbox_obj = composed.get("sandbox")
            if not isinstance(sandbox_obj, dict):
                sandbox_obj = {}
                composed["sandbox"] = sandbox_obj
            for path, incoming_values in current_sandbox_lists.items():
                merged_values = self._merge_unique_strings(
                    previous_sandbox_lists.get(path, []),
                    incoming_values,
                )
                self._set_nested_list(cast(dict[str, object], sandbox_obj), path, merged_values)
        return composed

    def _apply_bootstrap_sandbox_gating(self, *, composed_config: dict[str, object]) -> dict[str, object]:
        probe = load_claude_sandbox_probe(self._adapter.agent_manager.profile.agent_home)
        if probe is None or probe.available:
            return composed_config
        sandbox_obj = composed_config.get("sandbox")
        if not isinstance(sandbox_obj, dict):
            sandbox_obj = {}
            composed_config["sandbox"] = sandbox_obj
        sandbox_obj["enabled"] = False
        return composed_config

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        run_dir = ctx.run_dir
        options = ctx.options

        config_dir = run_dir / ".claude"
        settings_path = config_dir / "settings.json"

        engine_defaults: dict[str, object] = {}
        default_config_path = self._adapter.profile.resolve_default_config_path()
        if default_config_path.exists():
            try:
                payload = json.loads(default_config_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    engine_defaults = payload
            except _JSON_LOAD_EXCEPTIONS:
                logger.exception("Failed to load Claude engine defaults")

        skill_defaults: dict[str, object] = {}
        skill_config_resolution = resolve_engine_config_asset(
            skill,
            "claude",
            self._adapter.profile.config_assets.skill_defaults_path,
        )
        if skill_config_resolution.used_fallback and skill_config_resolution.issue_source == "declared":
            logger.warning(
                "Claude skill config declaration fallback: skill=%s declared=%s fallback=%s issue=%s",
                skill.id,
                skill_config_resolution.declared_relpath,
                skill_config_resolution.fallback_relpath,
                skill_config_resolution.issue_code,
            )
        payload = load_resolved_json(skill_config_resolution.path)
        if payload is not None:
            skill_defaults = payload

        runtime_overrides: dict[str, object] = {}
        if isinstance(options.get("claude_config"), dict):
            runtime_overrides = dict(options["claude_config"])
        model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            env_overrides = build_claude_model_env_overrides(model_obj)
            current_env = runtime_overrides.get("env")
            merged_env = dict(current_env) if isinstance(current_env, dict) else {}
            merged_env.update(env_overrides)
            runtime_overrides["env"] = merged_env

        enforced: dict[str, object] = {}
        enforced_path = self._adapter.profile.resolve_enforced_config_path()
        if enforced_path.exists():
            try:
                payload = json.loads(enforced_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    enforced = payload
            except _JSON_LOAD_EXCEPTIONS:
                logger.exception("Failed to load Claude enforced config")

        dynamic_enforced = self._build_dynamic_enforced_config(run_dir=run_dir)
        layers = [engine_defaults, skill_defaults, runtime_overrides, enforced, dynamic_enforced]
        composed_config = self._compose_layers(layers)
        composed_config = self._apply_bootstrap_sandbox_gating(composed_config=composed_config)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path = self._adapter.profile.resolve_settings_schema_path()
        if schema_path is None:
            raise RuntimeError("Claude adapter profile missing settings schema path")
        config_generator.generate_config(schema_path.name, [composed_config], settings_path)
        return settings_path
