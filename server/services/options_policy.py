import json
import logging
from pathlib import Path
from typing import Dict, Any

from ..config import config
from ..models import ExecutionMode
from .session_timeout import (
    LEGACY_SESSION_TIMEOUT_KEYS,
    SESSION_TIMEOUT_KEY,
    resolve_session_timeout,
)


class OptionsPolicy:
    def __init__(self) -> None:
        self._policy = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        policy_path = Path(config.SYSTEM.ROOT) / "server" / "assets" / "configs" / "options_policy.json"
        if policy_path.exists():
            with open(policy_path, "r") as f:
                return json.load(f)
        return {
            "runtime_options": [],
        }

    def validate_runtime_options(self, runtime_options: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(runtime_options)
        allowed_runtime = set(self._policy.get("runtime_options", []))
        self._validate_keys(normalized, allowed_runtime, "runtime_options")
        self._validate_execution_mode(normalized)
        self._validate_interactive_require_user_reply(normalized)
        self._validate_timeout_values(normalized)
        timeout_resolution = resolve_session_timeout(
            normalized,
            default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
        )
        normalized[SESSION_TIMEOUT_KEY] = timeout_resolution.value
        if timeout_resolution.deprecated_keys_used:
            logger.warning(
                "Deprecated timeout keys used: %s. Use %s instead.",
                ",".join(timeout_resolution.deprecated_keys_used),
                SESSION_TIMEOUT_KEY,
            )
        if timeout_resolution.legacy_keys_ignored:
            logger.warning(
                "Ignoring legacy timeout keys because %s is set: %s",
                SESSION_TIMEOUT_KEY,
                ",".join(timeout_resolution.legacy_keys_ignored),
            )
        for key in LEGACY_SESSION_TIMEOUT_KEYS:
            normalized.pop(key, None)
        normalized.setdefault("execution_mode", ExecutionMode.AUTO.value)
        if normalized.get("execution_mode") == ExecutionMode.INTERACTIVE.value:
            normalized.setdefault("interactive_require_user_reply", True)
        return normalized

    def _validate_keys(self, options: Dict[str, Any], allowed: set[str], label: str) -> None:
        unknown = [key for key in options.keys() if key not in allowed]
        if unknown:
            raise ValueError(f"Unknown {label}: {', '.join(sorted(unknown))}")

    def _validate_execution_mode(self, runtime_options: Dict[str, Any]) -> None:
        mode = runtime_options.get("execution_mode")
        if mode is None:
            return
        if not isinstance(mode, str):
            raise ValueError("runtime_options.execution_mode must be a string")
        allowed_modes = {ExecutionMode.AUTO.value, ExecutionMode.INTERACTIVE.value}
        if mode not in allowed_modes:
            raise ValueError(
                "runtime_options.execution_mode must be one of: auto, interactive"
            )

    def _validate_timeout_values(self, runtime_options: Dict[str, Any]) -> None:
        keys = [SESSION_TIMEOUT_KEY, *LEGACY_SESSION_TIMEOUT_KEYS]
        for key in keys:
            if key not in runtime_options:
                continue
            value = runtime_options.get(key)
            if value is None:
                raise ValueError(f"runtime_options.{key} must be a positive integer")
            try:
                parsed = int(value)
            except Exception as exc:
                raise ValueError(f"runtime_options.{key} must be a positive integer") from exc
            if parsed <= 0:
                raise ValueError(f"runtime_options.{key} must be a positive integer")

    def _validate_interactive_require_user_reply(self, runtime_options: Dict[str, Any]) -> None:
        if "interactive_require_user_reply" not in runtime_options:
            return
        value = runtime_options.get("interactive_require_user_reply")
        if isinstance(value, bool):
            return
        raise ValueError("runtime_options.interactive_require_user_reply must be a boolean")


options_policy = OptionsPolicy()
logger = logging.getLogger(__name__)
