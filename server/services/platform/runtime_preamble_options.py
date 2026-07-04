from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from server.config import config

PREAMBLE_PROMPT_KEY = "preamble_prompt"
INTERNAL_PREAMBLE_PROMPT_KEY = "__preamble_prompt"
RUNTIME_PREAMBLE_SECRET_MISSING = "RUNTIME_PREAMBLE_SECRET_MISSING"
RUNTIME_PREAMBLE_MAX_CHARS = 8000
_SAFE_REQUEST_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class RuntimePreambleSecretMissingError(RuntimeError):
    def __init__(self, request_id: str) -> None:
        super().__init__(
            f"{RUNTIME_PREAMBLE_SECRET_MISSING}: runtime preamble secret missing for request {request_id}"
        )
        self.code = RUNTIME_PREAMBLE_SECRET_MISSING
        self.request_id = request_id


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_runtime_preamble_prompt(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"runtime_options.{PREAMBLE_PROMPT_KEY} must be a string")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError(f"runtime_options.{PREAMBLE_PROMPT_KEY} must be a non-empty string")
    if len(normalized) > RUNTIME_PREAMBLE_MAX_CHARS:
        raise ValueError(
            f"runtime_options.{PREAMBLE_PROMPT_KEY} must be at most {RUNTIME_PREAMBLE_MAX_CHARS} characters"
        )
    for char in normalized:
        codepoint = ord(char)
        if codepoint < 32 and char not in {"\n", "\t"}:
            raise ValueError(
                f"runtime_options.{PREAMBLE_PROMPT_KEY} contains disallowed control characters"
            )
    return normalized


def redact_runtime_preamble_prompt(text: str) -> dict[str, Any]:
    normalized = normalize_runtime_preamble_prompt(text)
    return {
        "redacted": True,
        "sha256": _sha256_text(normalized),
        "length": len(normalized),
    }


def validate_runtime_preamble_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"runtime_options.{PREAMBLE_PROMPT_KEY} must be a string or redacted descriptor"
        )
    if value.get("redacted") is not True:
        raise ValueError(f"runtime_options.{PREAMBLE_PROMPT_KEY}.redacted must be true")
    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise ValueError(f"runtime_options.{PREAMBLE_PROMPT_KEY}.sha256 must be a sha256 hex digest")
    length = value.get("length")
    if isinstance(length, bool) or not isinstance(length, int):
        raise ValueError(f"runtime_options.{PREAMBLE_PROMPT_KEY}.length must be an integer")
    if length <= 0 or length > RUNTIME_PREAMBLE_MAX_CHARS:
        raise ValueError(
            f"runtime_options.{PREAMBLE_PROMPT_KEY}.length must be in 1..{RUNTIME_PREAMBLE_MAX_CHARS}"
        )
    return {"redacted": True, "sha256": sha256, "length": length}


def normalize_runtime_preamble_option(value: Any) -> str | dict[str, Any]:
    if isinstance(value, str):
        return normalize_runtime_preamble_prompt(value)
    return validate_runtime_preamble_descriptor(value)


def sanitize_runtime_options_preamble(
    runtime_options: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    sanitized = dict(runtime_options)
    if PREAMBLE_PROMPT_KEY not in sanitized:
        return sanitized, None
    value = sanitized.get(PREAMBLE_PROMPT_KEY)
    if isinstance(value, str):
        normalized = normalize_runtime_preamble_prompt(value)
        sanitized[PREAMBLE_PROMPT_KEY] = redact_runtime_preamble_prompt(normalized)
        return sanitized, normalized
    sanitized[PREAMBLE_PROMPT_KEY] = validate_runtime_preamble_descriptor(value)
    return sanitized, None


def preamble_prompt_hash_from_options(runtime_options: Any) -> str:
    if not isinstance(runtime_options, dict):
        return ""
    value = runtime_options.get(PREAMBLE_PROMPT_KEY)
    if value is None:
        return ""
    if isinstance(value, str):
        return _sha256_text(normalize_runtime_preamble_prompt(value))
    descriptor = validate_runtime_preamble_descriptor(value)
    return str(descriptor["sha256"])


def runtime_options_declare_preamble(runtime_options: Any) -> bool:
    if not isinstance(runtime_options, dict):
        return False
    return PREAMBLE_PROMPT_KEY in runtime_options


class RuntimePreambleSecretService:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root or (Path(config.SYSTEM.DATA_DIR) / "run_secrets")

    def _path_for(self, request_id: str) -> Path:
        safe_request_id = _SAFE_REQUEST_ID_RE.sub("_", request_id.strip())
        if not safe_request_id:
            raise ValueError("request_id is required for runtime preamble secret")
        return self.root / f"{safe_request_id}.preamble.json"

    def save(self, *, request_id: str, preamble_prompt: str | None) -> Path | None:
        if preamble_prompt is None:
            return None
        normalized = normalize_runtime_preamble_prompt(preamble_prompt)
        path = self._path_for(request_id)
        root = path.parent
        root.mkdir(parents=True, exist_ok=True)
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                {
                    "preamble_prompt": normalized,
                    "sha256": _sha256_text(normalized),
                    "length": len(normalized),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        try:
            root.chmod(0o700)
            path.chmod(0o600)
        except OSError:
            pass
        return path

    def load(self, *, request_id: str) -> str | None:
        path = self._path_for(request_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        value = payload.get("preamble_prompt")
        if not isinstance(value, str):
            return None
        normalized = normalize_runtime_preamble_prompt(value)
        expected = payload.get("sha256")
        if isinstance(expected, str) and expected != _sha256_text(normalized):
            raise ValueError("runtime preamble secret hash mismatch")
        return normalized

    def load_for_runtime_options(self, *, request_id: str, runtime_options: Any) -> str | None:
        if not runtime_options_declare_preamble(runtime_options):
            return None
        value = runtime_options.get(PREAMBLE_PROMPT_KEY) if isinstance(runtime_options, dict) else None
        if isinstance(value, str):
            return normalize_runtime_preamble_prompt(value)
        validate_runtime_preamble_descriptor(value)
        loaded = self.load(request_id=request_id)
        if loaded is None:
            raise RuntimePreambleSecretMissingError(request_id)
        return loaded

    def delete(self, *, request_id: str) -> None:
        self._path_for(request_id).unlink(missing_ok=True)


runtime_preamble_secret_service = RuntimePreambleSecretService()
