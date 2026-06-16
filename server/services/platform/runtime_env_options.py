from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from server.config import config

RUNTIME_ENV_SECRET_MISSING = "RUNTIME_ENV_SECRET_MISSING"
RUNTIME_ENV_MAX_VARS = 64
RUNTIME_ENV_MAX_VALUE_CHARS = 8192
RUNTIME_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
RUNTIME_ENV_PROTECTED_NAMES = {
    "PATH",
    "HOME",
    "SHELL",
    "PWD",
    "OLDPWD",
    "USER",
    "USERNAME",
    "LOGNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "PYTHONPATH",
    "LD_LIBRARY_PATH",
}

_SAFE_REQUEST_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


class RuntimeEnvSecretMissingError(RuntimeError):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            f"{RUNTIME_ENV_SECRET_MISSING}: runtime env secret missing for request {request_id}"
        )
        self.code = RUNTIME_ENV_SECRET_MISSING
        self.request_id = request_id


def _validate_env_name(name: Any) -> str:
    if not isinstance(name, str) or not RUNTIME_ENV_NAME_RE.fullmatch(name):
        raise ValueError(
            "runtime_options.env keys must match ^[A-Z_][A-Z0-9_]{0,127}$"
        )
    if name in RUNTIME_ENV_PROTECTED_NAMES:
        raise ValueError(f"runtime_options.env.{name} is protected and cannot be overridden")
    return name


def _is_redacted_value(value: Any) -> bool:
    return isinstance(value, dict) and value.get("redacted") is True


def validate_runtime_env(env: Any, *, allow_redacted: bool = True) -> dict[str, Any]:
    if not isinstance(env, dict):
        raise ValueError("runtime_options.env must be an object")
    if len(env) > RUNTIME_ENV_MAX_VARS:
        raise ValueError(f"runtime_options.env must contain at most {RUNTIME_ENV_MAX_VARS} variables")
    normalized: dict[str, Any] = {}
    for raw_name, raw_value in env.items():
        name = _validate_env_name(raw_name)
        if isinstance(raw_value, str):
            if len(raw_value) > RUNTIME_ENV_MAX_VALUE_CHARS:
                raise ValueError(
                    f"runtime_options.env.{name} must be at most {RUNTIME_ENV_MAX_VALUE_CHARS} characters"
                )
            normalized[name] = raw_value
            continue
        if allow_redacted and _is_redacted_value(raw_value):
            normalized[name] = {"redacted": True}
            continue
        raise ValueError(f"runtime_options.env.{name} must be a string")
    return normalized


def is_redacted_runtime_env(env: Any) -> bool:
    return isinstance(env, dict) and bool(env) and all(
        _is_redacted_value(value) for value in env.values()
    )


def redact_runtime_env(env: dict[str, Any]) -> dict[str, dict[str, bool]]:
    return {name: {"redacted": True} for name in sorted(validate_runtime_env(env).keys())}


def sanitize_runtime_options_env(
    runtime_options: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str] | None]:
    sanitized = dict(runtime_options)
    if "env" not in sanitized:
        return sanitized, None
    normalized = validate_runtime_env(sanitized.get("env"))
    raw_values = {
        name: value for name, value in normalized.items() if isinstance(value, str)
    }
    if raw_values:
        sanitized["env"] = redact_runtime_env(raw_values)
        return sanitized, raw_values
    sanitized["env"] = redact_runtime_env(normalized)
    return sanitized, None


def runtime_options_declare_env(runtime_options: Any) -> bool:
    if not isinstance(runtime_options, dict):
        return False
    env = runtime_options.get("env")
    return isinstance(env, dict) and bool(env)


class RuntimeEnvSecretService:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root or (Path(config.SYSTEM.DATA_DIR) / "run_secrets")

    def _path_for(self, request_id: str) -> Path:
        safe_request_id = _SAFE_REQUEST_ID_RE.sub("_", request_id.strip())
        if not safe_request_id:
            raise ValueError("request_id is required for runtime env secret")
        return self.root / f"{safe_request_id}.env.json"

    def save(self, *, request_id: str, env: dict[str, str] | None) -> Path | None:
        if not env:
            return None
        normalized = validate_runtime_env(env, allow_redacted=False)
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        with os.fdopen(
            os.open(self._path_for(request_id), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(normalized, handle, sort_keys=True)
        try:
            root.chmod(0o700)
            self._path_for(request_id).chmod(0o600)
        except OSError:
            pass
        return self._path_for(request_id)

    def load(self, *, request_id: str) -> dict[str, str]:
        path = self._path_for(request_id)
        if not path.exists():
            raise RuntimeEnvSecretMissingError(request_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeEnvSecretMissingError(request_id) from exc
        normalized = validate_runtime_env(payload, allow_redacted=False)
        return {name: str(value) for name, value in normalized.items()}

    def load_for_runtime_options(
        self,
        *,
        request_id: str,
        runtime_options: Any,
    ) -> dict[str, str]:
        if not runtime_options_declare_env(runtime_options):
            return {}
        return self.load(request_id=request_id)

    def delete(self, *, request_id: str) -> None:
        try:
            self._path_for(request_id).unlink(missing_ok=True)
        except OSError:
            pass

    def delete_many(self, request_ids: list[str]) -> None:
        for request_id in request_ids:
            self.delete(request_id=request_id)

    def clear_all(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


runtime_env_secret_service = RuntimeEnvSecretService()
