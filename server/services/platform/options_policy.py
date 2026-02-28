import json
import logging
from pathlib import Path
from typing import Dict, Any

from server.config import config
from server.models import ExecutionMode
from server.runtime.session.timeout import (
    INTERACTIVE_REPLY_TIMEOUT_KEY,
    resolve_interactive_reply_timeout,
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
        self._validate_interactive_auto_reply(normalized)
        self._validate_timeout_values(normalized)
        timeout_resolution = resolve_interactive_reply_timeout(
            normalized,
            default=int(config.SYSTEM.SESSION_TIMEOUT_SEC),
        )
        normalized[INTERACTIVE_REPLY_TIMEOUT_KEY] = timeout_resolution.value
        normalized.setdefault("execution_mode", ExecutionMode.AUTO.value)
        normalized.setdefault("interactive_auto_reply", False)
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
        if INTERACTIVE_REPLY_TIMEOUT_KEY not in runtime_options:
            return
        value = runtime_options.get(INTERACTIVE_REPLY_TIMEOUT_KEY)
        if value is None:
            raise ValueError(
                f"runtime_options.{INTERACTIVE_REPLY_TIMEOUT_KEY} must be a positive integer"
            )
        try:
            parsed = int(value)
        except Exception as exc:
            raise ValueError(
                f"runtime_options.{INTERACTIVE_REPLY_TIMEOUT_KEY} must be a positive integer"
            ) from exc
        if parsed <= 0:
            raise ValueError(
                f"runtime_options.{INTERACTIVE_REPLY_TIMEOUT_KEY} must be a positive integer"
            )

    def _validate_interactive_auto_reply(self, runtime_options: Dict[str, Any]) -> None:
        if "interactive_auto_reply" not in runtime_options:
            return
        value = runtime_options.get("interactive_auto_reply")
        if isinstance(value, bool):
            return
        raise ValueError("runtime_options.interactive_auto_reply must be a boolean")


options_policy = OptionsPolicy()
logger = logging.getLogger(__name__)
