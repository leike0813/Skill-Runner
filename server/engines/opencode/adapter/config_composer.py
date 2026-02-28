from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.contracts import AdapterExecutionContext

if TYPE_CHECKING:
    from .execution_adapter import OpencodeExecutionAdapter

logger = logging.getLogger(__name__)


class OpencodeConfigComposer:
    def __init__(self, adapter: "OpencodeExecutionAdapter") -> None:
        self._adapter = adapter

    def _load_json_config(self, config_path: Path, *, label: str) -> dict[str, Any]:
        if not config_path.exists():
            return {}
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
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

    def _mode_permission_overlay(self, options: dict[str, Any]) -> dict[str, Any]:
        execution_mode = self._adapter._resolve_execution_mode(options)  # noqa: SLF001
        question_mode = "allow" if execution_mode == "interactive" else "deny"
        return {"permission": {"question": question_mode}}

    def compose(self, ctx: AdapterExecutionContext) -> Path:
        skill = ctx.skill
        run_dir = ctx.run_dir
        options = ctx.options

        layers: list[dict[str, Any]] = []
        engine_default_path = self._adapter.profile.resolve_default_config_path()
        layers.append(self._load_json_config(engine_default_path, label="opencode default"))

        skill_defaults: dict[str, Any] = {}
        candidate = self._adapter.profile.resolve_skill_defaults_path(skill.path)
        if candidate is not None:
            if candidate.exists():
                skill_defaults = self._load_json_config(candidate, label="opencode skill default")
        layers.append(skill_defaults)

        runtime_override: dict[str, Any] = {}
        if isinstance(options.get("opencode_config"), dict):
            runtime_override = options["opencode_config"]
        layers.append(runtime_override)

        enforced_path = self._adapter.profile.resolve_enforced_config_path()
        layers.append(self._load_json_config(enforced_path, label="opencode enforced"))
        layers.append(self._mode_permission_overlay(options))

        merged: dict[str, Any] = {}
        for layer in layers:
            if isinstance(layer, dict):
                self._deep_merge_dicts(merged, layer)

        config_path = run_dir / "opencode.json"
        config_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config_path
