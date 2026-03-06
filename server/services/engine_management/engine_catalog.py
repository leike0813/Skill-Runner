from __future__ import annotations

from server.config_registry import keys


SUPPORTED_ENGINES: tuple[str, ...] = tuple(str(engine).strip().lower() for engine in keys.ENGINE_KEYS)


def supported_engines() -> tuple[str, ...]:
    return SUPPORTED_ENGINES


def normalize_engine_name(engine: str) -> str:
    return engine.strip().lower()


def is_supported_engine(engine: str) -> bool:
    return normalize_engine_name(engine) in SUPPORTED_ENGINES

