from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PORT = 8011
PORT_ENV = "SKILL_RUNNER_E2E_CLIENT_PORT"
BACKEND_BASE_URL_ENV = "SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL"
HOST_ENV = "SKILL_RUNNER_E2E_CLIENT_HOST"
RECORDINGS_DIR_ENV = "SKILL_RUNNER_E2E_CLIENT_RECORDINGS_DIR"


@dataclass(frozen=True)
class E2EClientSettings:
    host: str
    port: int
    backend_base_url: str
    recordings_dir: Path


def load_settings() -> E2EClientSettings:
    host = os.environ.get(HOST_ENV, "127.0.0.1").strip() or "127.0.0.1"
    port = _parse_port(
        os.environ.get(PORT_ENV),
        default=DEFAULT_PORT,
    )
    backend_base_url = (
        os.environ.get(BACKEND_BASE_URL_ENV, "http://127.0.0.1:8000").strip()
        or "http://127.0.0.1:8000"
    )
    recordings_dir_raw = os.environ.get(RECORDINGS_DIR_ENV, "").strip()
    if recordings_dir_raw:
        recordings_dir = Path(recordings_dir_raw).expanduser()
    else:
        recordings_dir = Path(__file__).resolve().parent / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    return E2EClientSettings(
        host=host,
        port=port,
        backend_base_url=backend_base_url.rstrip("/"),
        recordings_dir=recordings_dir,
    )


def _parse_port(raw: str | None, *, default: int) -> int:
    if raw is None:
        return default
    text = raw.strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        return default
    if value < 1 or value > 65535:
        return default
    return value

