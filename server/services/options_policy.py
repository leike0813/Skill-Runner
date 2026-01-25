import json
from pathlib import Path
from typing import Dict, Any

from ..config import config


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
        allowed_runtime = set(self._policy.get("runtime_options", []))
        self._validate_keys(runtime_options, allowed_runtime, "runtime_options")
        return runtime_options

    def _validate_keys(self, options: Dict[str, Any], allowed: set[str], label: str) -> None:
        unknown = [key for key in options.keys() if key not in allowed]
        if unknown:
            raise ValueError(f"Unknown {label}: {', '.join(sorted(unknown))}")


options_policy = OptionsPolicy()
