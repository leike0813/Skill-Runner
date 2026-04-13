from __future__ import annotations

from collections.abc import Mapping


RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH = "__target_output_schema_relpath"


def resolve_output_schema_relpath(options: Mapping[str, object]) -> str | None:
    raw = options.get(RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def build_claude_output_schema_args(options: Mapping[str, object]) -> list[str]:
    relpath = resolve_output_schema_relpath(options)
    if relpath is None:
        return []
    return ["--json-schema", relpath]


def build_codex_output_schema_args(options: Mapping[str, object]) -> list[str]:
    relpath = resolve_output_schema_relpath(options)
    if relpath is None:
        return []
    return ["--output-schema", relpath]
