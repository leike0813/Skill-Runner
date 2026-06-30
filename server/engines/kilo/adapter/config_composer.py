from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.contracts import AdapterExecutionContext
from server.services.mcp import build_mcp_config_layer, validate_no_mcp_root_keys
from server.services.skill.skill_asset_resolver import (
    load_resolved_json,
    resolve_engine_config_asset,
)

if TYPE_CHECKING:
    from .execution_adapter import KiloExecutionAdapter

logger = logging.getLogger(__name__)

RUNNER_ONLY_OPTION_KEYS = {
    "no_cache",
    "execution_mode",
    "interactive_auto_reply",
    "interactive_reply_timeout_sec",
    "hard_timeout_seconds",
}


class KiloConfigComposer:
    def __init__(self, adapter: "KiloExecutionAdapter") -> None:
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

    def _validate_user_roots(self, payload: dict[str, Any], *, source: str) -> None:
        validate_no_mcp_root_keys(payload, source=source)

    def _model_overlay(self, options: dict[str, Any]) -> dict[str, Any]:
        model_obj = options.get("runtime_model")
        if not isinstance(model_obj, str) or not model_obj.strip():
            model_obj = options.get("model")
        if isinstance(model_obj, str) and model_obj.strip():
            return {"model": model_obj.strip()}
        return {}

    def extract_kilo_overrides(self, options: dict[str, Any]) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        raw_kilo_config = options.get("kilo_config")
        if isinstance(raw_kilo_config, dict):
            for key, value in raw_kilo_config.items():
                if not isinstance(key, str):
                    continue
                if key.startswith("__") or key in RUNNER_ONLY_OPTION_KEYS:
                    continue
                overrides[key] = value
        return overrides

    def _ensure_run_skill_path(self, config: dict[str, Any], run_dir: Path) -> None:
        workspace = self._adapter.profile.attempt_workspace
        skills_root = (run_dir / workspace.workspace_subdir / workspace.skills_subdir).resolve()
        if not skills_root.exists():
            return

        skills_config = config.get("skills")
        if not isinstance(skills_config, dict):
            skills_config = {}
            config["skills"] = skills_config

        existing_paths = skills_config.get("paths")
        if not isinstance(existing_paths, list):
            existing_paths = []

        normalized_paths = [item for item in existing_paths if isinstance(item, str) and item.strip()]
        skills_root_text = str(skills_root)
        if skills_root_text not in normalized_paths:
            normalized_paths.append(skills_root_text)
        skills_config["paths"] = normalized_paths

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        options = ctx.options

        layers: list[dict[str, Any]] = [
            self._load_json_config(
                self._adapter.profile.resolve_default_config_path(),
                label="kilo default",
            )
        ]

        skill_defaults: dict[str, Any] = {}
        if skill.path:
            config_resolution = resolve_engine_config_asset(
                skill,
                "kilo",
                self._adapter.profile.config_assets.skill_defaults_path,
            )
            if config_resolution.used_fallback and config_resolution.issue_source == "declared":
                logger.warning(
                    "Kilo skill config declaration fallback: skill=%s declared=%s fallback=%s issue=%s",
                    skill.id,
                    config_resolution.declared_relpath,
                    config_resolution.fallback_relpath,
                    config_resolution.issue_code,
                )
            payload = load_resolved_json(config_resolution.path)
            if payload is not None:
                skill_defaults = payload
        self._validate_user_roots(skill_defaults, source="Kilo skill config")
        layers.append(skill_defaults)

        runtime_overrides = self.extract_kilo_overrides(options)
        self._validate_user_roots(runtime_overrides, source="Kilo runtime override")
        layers.append(runtime_overrides)
        layers.append(self._model_overlay(options))
        _, governed_mcp = build_mcp_config_layer(skill=skill, engine="kilo")
        layers.append(governed_mcp)
        layers.append(
            self._load_json_config(
                self._adapter.profile.resolve_enforced_config_path(),
                label="kilo enforced",
            )
        )

        fused_config: dict[str, Any] = {}
        for layer in layers:
            if isinstance(layer, dict):
                self._deep_merge_dicts(fused_config, layer)
        self._ensure_run_skill_path(fused_config, ctx.run_dir)

        config_path = self._write_config(fused_config, ctx.run_dir)
        logger.info("Composed Kilo configuration at %s", config_path)
        return config_path

    def _write_config(self, config: dict[str, Any], run_dir: Path) -> Path:
        kilo_dir = run_dir / ".kilo"
        kilo_dir.mkdir(parents=True, exist_ok=True)
        config_path = kilo_dir / "kilo.jsonc"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return config_path
