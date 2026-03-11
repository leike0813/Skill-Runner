from __future__ import annotations

import re
from typing import Any

DEFAULT_INTERACTION_PROMPT = "Please reply to continue."

ASK_USER_BLOCK_PATTERNS = (
    re.compile(
        r"<ASK_USER_YAML>\s*[\s\S]*?\s*</ASK_USER_YAML>",
        re.IGNORECASE,
    ),
    re.compile(
        r"```(?:ask_user_yaml|ask-user-yaml)\s*[\s\S]*?```",
        re.IGNORECASE,
    ),
)


def strip_ask_user_yaml_blocks(text: str) -> str:
    normalized = str(text or "")
    for pattern in ASK_USER_BLOCK_PATTERNS:
        normalized = pattern.sub("\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def normalize_interaction_text(raw_text: Any) -> str:
    if not isinstance(raw_text, str):
        return ""
    return strip_ask_user_yaml_blocks(raw_text).strip()


def contains_ask_user_yaml_block(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    normalized = str(text or "")
    return any(pattern.search(normalized) for pattern in ASK_USER_BLOCK_PATTERNS)
