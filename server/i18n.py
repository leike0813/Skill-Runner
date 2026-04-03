from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import Request

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED_LANGUAGES = ("zh", "en", "fr", "ja")
DEFAULT_LANGUAGE = "zh"

_translations: dict[str, dict[str, Any]] = {}

# Keys that should always render from English baseline and are not translated per locale.
NON_LOCALIZED_PREFIXES: tuple[str, ...] = ()
NON_LOCALIZED_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "ui.engines.engine_codex",
        "ui.engines.engine_gemini",
        "ui.engines.engine_iflow",
        "ui.engines.engine_opencode",
        "ui.engines.engine_claude",
        "ui.engines.method_api_key",
        "ui.engines.method_auth_code",
        "ui.engines.method_callback",
        "ui.engines.transport_cli_delegate",
        "ui.engines.transport_oauth_proxy",
    }
)


def load_translations() -> None:
    global _translations
    loaded: dict[str, dict[str, Any]] = {}
    for lang in SUPPORTED_LANGUAGES:
        path = LOCALES_DIR / f"{lang}.json"
        if not path.exists():
            loaded[lang] = {}
            continue
        try:
            loaded[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded[lang] = {}
    _translations = loaded


def get_language(request: Request) -> str:
    query_lang = request.query_params.get("lang", "").strip().lower()
    if query_lang in SUPPORTED_LANGUAGES:
        return query_lang

    cookie_lang = request.cookies.get("lang", "").strip().lower()
    if cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang

    accept_language = request.headers.get("accept-language", "")
    if accept_language:
        primary = accept_language.split(",", 1)[0].split(";", 1)[0].strip().lower()
        primary_short = primary.split("-", 1)[0]
        if primary_short in SUPPORTED_LANGUAGES:
            return primary_short

    return DEFAULT_LANGUAGE


def _lookup_translation(lang: str, key: str) -> str | None:
    current: Any = _translations.get(lang, {})
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current if isinstance(current, str) else None


def is_non_localized_key(key: str) -> bool:
    return key in NON_LOCALIZED_EXACT_KEYS or any(key.startswith(prefix) for prefix in NON_LOCALIZED_PREFIXES)


def get_translator(request: Request) -> Callable[..., str]:
    lang = get_language(request)

    def t(key: str, default: str | None = None, **kwargs: Any) -> str:
        if is_non_localized_key(key):
            text = _lookup_translation("en", key)
        else:
            text = _lookup_translation(lang, key)
            if text is None and lang != "en":
                text = _lookup_translation("en", key)
            if text is None and DEFAULT_LANGUAGE not in {lang, "en"}:
                text = _lookup_translation(DEFAULT_LANGUAGE, key)
        if text is None:
            text = default if default is not None else key
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text

    return t


load_translations()
