from dataclasses import dataclass
from typing import Any

from .model_registry import supported_engines


@dataclass(frozen=True)
class SkillEnginePolicy:
    declared_engines: list[str]
    unsupported_engines: list[str]
    effective_engines: list[str]


def resolve_engine_policy(
    declared_engines: Any,
    unsupported_engines: Any,
) -> SkillEnginePolicy:
    allowed = supported_engines()
    allowed_set = set(allowed)
    declared = _normalize_engine_list(declared_engines, "engines")
    unsupported = _normalize_engine_list(unsupported_engines, "unsupported_engines")

    unknown = sorted((set(declared) | set(unsupported)) - allowed_set)
    if unknown:
        raise ValueError(
            "runner.json engines/unsupported_engines must contain only: "
            + ", ".join(allowed)
        )

    overlap = sorted(set(declared) & set(unsupported))
    if overlap:
        raise ValueError(
            "runner.json engines and unsupported_engines must not overlap: "
            + ", ".join(overlap)
        )

    # Omitted engines defaults to all supported engines.
    declared_base = declared if declared else list(allowed)
    deny_set = set(unsupported)
    effective = [engine for engine in declared_base if engine not in deny_set]
    if not effective:
        raise ValueError("runner.json effective engines must not be empty")

    return SkillEnginePolicy(
        declared_engines=declared,
        unsupported_engines=unsupported,
        effective_engines=effective,
    )


def apply_engine_policy_to_manifest(manifest: dict[str, Any]) -> SkillEnginePolicy:
    if "unsupport_engine" in manifest:
        raise ValueError(
            "runner.json field 'unsupport_engine' has been renamed to "
            "'unsupported_engines'"
        )
    policy = resolve_engine_policy(
        manifest.get("engines"),
        manifest.get("unsupported_engines"),
    )
    manifest["engines"] = policy.declared_engines
    manifest["unsupported_engines"] = policy.unsupported_engines
    manifest["effective_engines"] = policy.effective_engines
    return policy


def resolve_skill_engine_policy(skill: Any) -> SkillEnginePolicy:
    effective_existing = _normalize_engine_list(
        getattr(skill, "effective_engines", None),
        "effective_engines",
    )
    declared = _normalize_engine_list(getattr(skill, "engines", None), "engines")
    unsupported = _normalize_engine_list(
        getattr(skill, "unsupported_engines", None),
        "unsupported_engines",
    )
    if effective_existing and declared:
        return SkillEnginePolicy(
            declared_engines=declared,
            unsupported_engines=unsupported,
            effective_engines=effective_existing,
        )
    return resolve_engine_policy(declared, unsupported)


def _normalize_engine_list(raw: Any, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"runner.json {field_name} must be a list when provided")
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"runner.json {field_name} must contain non-empty strings"
            )
        normalized.append(item.strip())
    return list(dict.fromkeys(normalized))
