from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from server.engines.claude.adapter.config_composer import build_claude_model_env_overrides
from server.engines.common.config.json_layer_config_generator import config_generator
from server.runtime.adapter.common.profile_loader import AdapterProfile

logger = logging.getLogger(__name__)

_JSON_LOAD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)


class UiShellRuntimeOverrideStrategy(Protocol):
    def build(
        self,
        *,
        session_dir: Path,
        sandbox_enabled: bool,
        custom_model: str | None,
    ) -> dict[str, object]:
        ...


class _NoopRuntimeOverride:
    def build(
        self,
        *,
        session_dir: Path,
        sandbox_enabled: bool,
        custom_model: str | None,
    ) -> dict[str, object]:
        _ = (session_dir, sandbox_enabled, custom_model)
        return {}


class _GeminiUiShellRuntimeOverride:
    def build(
        self,
        *,
        session_dir: Path,
        sandbox_enabled: bool,
        custom_model: str | None,
    ) -> dict[str, object]:
        _ = (session_dir, custom_model)
        return {"tools": {"sandbox": sandbox_enabled}}


class _ClaudeUiShellRuntimeOverride:
    def build(
        self,
        *,
        session_dir: Path,
        sandbox_enabled: bool,
        custom_model: str | None,
    ) -> dict[str, object]:
        _ = session_dir
        runtime: dict[str, object] = {"sandbox": {"enabled": sandbox_enabled}}
        if isinstance(custom_model, str) and custom_model.strip():
            runtime["env"] = build_claude_model_env_overrides(custom_model)
        return runtime


_RUNTIME_OVERRIDE_REGISTRY: dict[str, UiShellRuntimeOverrideStrategy] = {
    "none": _NoopRuntimeOverride(),
    "gemini_ui_shell": _GeminiUiShellRuntimeOverride(),
    "claude_ui_shell": _ClaudeUiShellRuntimeOverride(),
}


def _load_json_object(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except _JSON_LOAD_EXCEPTIONS:
        logger.exception("Failed to load ui_shell config asset: %s", path)
        return {}
    if isinstance(payload, dict):
        return payload
    logger.warning("ui_shell config asset must be a JSON object: %s", path)
    return {}


def _write_merged_json(path: Path, layers: list[dict[str, object]]) -> None:
    merged: dict[str, object] = {}
    for layer in layers:
        merged = config_generator.deep_merge(merged, dict(layer))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class ProfiledJsonSessionSecurity:
    def __init__(self, profile: AdapterProfile) -> None:
        self._profile = profile
        self._runtime_override_strategy = _RUNTIME_OVERRIDE_REGISTRY[profile.ui_shell.runtime_override_strategy]

    def prepare(
        self,
        *,
        session_dir: Path,
        env: dict[str, str],
        sandbox_enabled: bool,
        custom_model: str | None = None,
    ) -> None:
        _ = env
        target_relpath = self._profile.resolve_ui_shell_target_relpath()
        if target_relpath is None:
            return

        default_layer = _load_json_object(self._profile.resolve_ui_shell_default_config_path())
        runtime_layer = self._runtime_override_strategy.build(
            session_dir=session_dir,
            sandbox_enabled=sandbox_enabled,
            custom_model=custom_model,
        )
        enforced_layer = _load_json_object(self._profile.resolve_ui_shell_enforced_config_path())
        target_path = session_dir / target_relpath
        schema_path = self._profile.resolve_ui_shell_settings_schema_path()

        if schema_path is None:
            _write_merged_json(target_path, [default_layer, runtime_layer, enforced_layer])
            return

        config_generator.generate_config(
            schema_name=schema_path.name,
            config_layers=[default_layer, runtime_layer, enforced_layer],
            output_path=target_path,
        )
