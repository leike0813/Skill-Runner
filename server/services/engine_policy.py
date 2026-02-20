from dataclasses import dataclass
from typing import Any

from .model_registry import supported_engines


@dataclass(frozen=True)
class SkillEnginePolicy:
    declared_engines: list[str]
    unsupport_engine: list[str]
    effective_engines: list[str]


def resolve_engine_policy(
    declared_engines: Any,
    unsupport_engine: Any,
) -> SkillEnginePolicy:
    allowed = supported_engines()
    allowed_set = set(allowed)
    declared = _normalize_engine_list(declared_engines, "engines")
    unsupported = _normalize_engine_list(unsupport_engine, "unsupport_engine")

    unknown = sorted((set(declared) | set(unsupported)) - allowed_set)
    if unknown:
        raise ValueError(
            "runner.json engines/unsupport_engine must contain only: "
            + ", ".join(allowed)
        )

    overlap = sorted(set(declared) & set(unsupported))
    if overlap:
        raise ValueError(
            "runner.json engines and unsupport_engine must not overlap: "
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
        unsupport_engine=unsupported,
        effective_engines=effective,
    )


def apply_engine_policy_to_manifest(manifest: dict[str, Any]) -> SkillEnginePolicy:
    policy = resolve_engine_policy(
        manifest.get("engines"),
        manifest.get("unsupport_engine"),
    )
    manifest["engines"] = policy.declared_engines
    manifest["unsupport_engine"] = policy.unsupport_engine
    manifest["effective_engines"] = policy.effective_engines
    return policy


def resolve_skill_engine_policy(skill: Any) -> SkillEnginePolicy:
    effective_existing = _normalize_engine_list(
        getattr(skill, "effective_engines", None),
        "effective_engines",
    )
    declared = _normalize_engine_list(getattr(skill, "engines", None), "engines")
    unsupported = _normalize_engine_list(
        getattr(skill, "unsupport_engine", None),
        "unsupport_engine",
    )
    if effective_existing and declared:
        return SkillEnginePolicy(
            declared_engines=declared,
            unsupport_engine=unsupported,
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
