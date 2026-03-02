from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from server.config import config


def _profile_path() -> Path:
    return Path(config.SYSTEM.ROOT) / "server" / "assets" / "configs" / "engine_command_profiles.json"


def _token_key(token: str) -> str:
    if token.startswith("--") and "=" in token:
        return token.split("=", 1)[0]
    return token


def _parse_tokens(args: list[str]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("-"):
            if token.startswith("--") and "=" in token:
                parsed.append({"kind": "option", "key": _token_key(token), "tokens": [token]})
                index += 1
                continue
            if index + 1 < len(args) and not args[index + 1].startswith("-"):
                parsed.append(
                    {
                        "kind": "option",
                        "key": _token_key(token),
                        "tokens": [token, args[index + 1]],
                    }
                )
                index += 2
                continue
            parsed.append({"kind": "option", "key": _token_key(token), "tokens": [token]})
            index += 1
            continue
        parsed.append({"kind": "positional", "tokens": [token]})
        index += 1
    return parsed


def merge_cli_args(default_args: list[str], explicit_args: list[str]) -> list[str]:
    default_parsed = _parse_tokens(default_args)
    explicit_parsed = _parse_tokens(explicit_args)
    explicit_keys = {
        item["key"]
        for item in explicit_parsed
        if item.get("kind") == "option" and isinstance(item.get("key"), str)
    }
    merged: list[str] = []
    for item in default_parsed:
        if item.get("kind") == "option" and item.get("key") in explicit_keys:
            continue
        merged.extend([str(token) for token in item.get("tokens", [])])
    for item in explicit_parsed:
        merged.extend([str(token) for token in item.get("tokens", [])])
    return merged


class EngineCommandProfile:
    def __init__(self, profile_path: Path | None = None) -> None:
        self.profile_path = profile_path or _profile_path()

    @lru_cache(maxsize=1)
    def _load(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return {}
        payload = json.loads(self.profile_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return payload

    def clear_cache(self) -> None:
        self._load.cache_clear()

    def resolve_args(self, *, engine: str, action: str) -> list[str]:
        payload = self._load()
        engine_profile = payload.get(engine)
        if not isinstance(engine_profile, dict):
            return []
        action_args = engine_profile.get(action)
        if not isinstance(action_args, list):
            return []
        return [str(token) for token in action_args if isinstance(token, (str, int, float))]


engine_command_profile = EngineCommandProfile()
