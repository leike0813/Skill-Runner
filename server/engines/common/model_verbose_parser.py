from __future__ import annotations

import json
from typing import Any


def extract_model_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        models_obj = payload.get("models")
        if isinstance(models_obj, list):
            return [item for item in models_obj if isinstance(item, dict)]
        if isinstance(payload.get("id"), str) or isinstance(payload.get("model"), str):
            return [payload]
    return []


def extract_labeled_json_rows(stdout_text: str, *, error_label: str) -> list[tuple[str | None, dict[str, Any]]]:
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return extract_labeled_json_blocks(stdout_text, error_label=error_label)
    return [(None, row) for row in extract_model_rows(payload)]


def extract_labeled_json_blocks(stdout_text: str, *, error_label: str) -> list[tuple[str | None, dict[str, Any]]]:
    decoder = json.JSONDecoder()
    rows: list[tuple[str | None, dict[str, Any]]] = []
    position = 0
    text_len = len(stdout_text)
    while position < text_len:
        while position < text_len and stdout_text[position].isspace():
            position += 1
        if position >= text_len:
            break

        label: str | None = None
        if stdout_text[position] != "{":
            line_end = stdout_text.find("\n", position)
            if line_end == -1:
                break
            candidate = stdout_text[position:line_end].strip()
            position = line_end + 1
            if candidate:
                label = candidate
            while position < text_len and stdout_text[position].isspace():
                position += 1

        if position >= text_len or stdout_text[position] != "{":
            continue
        try:
            payload, next_position = decoder.raw_decode(stdout_text, position)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{error_label} returned malformed object blocks") from exc
        if isinstance(payload, dict):
            rows.append((label, payload))
        position = next_position
    return rows
