from __future__ import annotations

from collections.abc import Mapping


RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH = "__target_output_schema_relpath"


def resolve_output_schema_relpath(options: Mapping[str, object]) -> str | None:
    raw = options.get(RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None
