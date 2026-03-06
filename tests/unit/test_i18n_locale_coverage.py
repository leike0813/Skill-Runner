from __future__ import annotations

import json
import re
from pathlib import Path

from server.i18n import SUPPORTED_LANGUAGES, is_non_localized_key


_T_CALL_PATTERN = re.compile(r"""\bt\(\s*['"]([^'"]+)['"]""")
_TEMPLATE_ROOTS = (
    Path("server/assets/templates/ui"),
    Path("e2e_client/templates"),
)


def _flatten_translation_keys(node: object, prefix: str = "") -> set[str]:
    if not isinstance(node, dict):
        return set()
    keys: set[str] = set()
    for key, value in node.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys.update(_flatten_translation_keys(value, full_key))
        elif isinstance(value, str):
            keys.add(full_key)
    return keys


def _extract_template_translation_keys() -> set[str]:
    keys: set[str] = set()
    for root in _TEMPLATE_ROOTS:
        for path in root.rglob("*.html"):
            content = path.read_text(encoding="utf-8")
            keys.update(_T_CALL_PATTERN.findall(content))
    return keys


def test_all_template_translation_keys_exist_in_english_locale() -> None:
    template_keys = _extract_template_translation_keys()
    assert template_keys, "No translation keys found in templates."

    payload = json.loads(Path("server/locales/en.json").read_text(encoding="utf-8"))
    locale_keys = _flatten_translation_keys(payload)
    missing = sorted(template_keys - locale_keys)
    assert not missing, f"Locale 'en' missing keys: {missing[:20]}"


def test_non_english_locales_cover_all_localizable_template_keys() -> None:
    template_keys = _extract_template_translation_keys()
    assert template_keys, "No translation keys found in templates."

    for lang in SUPPORTED_LANGUAGES:
        if lang == "en":
            continue
        locale_path = Path("server/locales") / f"{lang}.json"
        payload = json.loads(locale_path.read_text(encoding="utf-8"))
        locale_keys = _flatten_translation_keys(payload)
        missing = sorted(template_keys - locale_keys)
        invalid_missing = [key for key in missing if not is_non_localized_key(key)]
        assert not invalid_missing, f"Locale '{lang}' missing localizable keys: {invalid_missing[:20]}"


def test_non_localized_key_policy_basic_scope() -> None:
    assert not is_non_localized_key("nav.home")
    assert is_non_localized_key("ui.engines.method_api_key")
    assert not is_non_localized_key("ui.runs.title")
