from __future__ import annotations

from typing import Any

from fastapi import HTTPException  # type: ignore[import-not-found]

from server.models import ExecutionMode
from server.services.orchestration.engine_policy import SkillEnginePolicy
from server.services.orchestration.model_registry import model_registry
from server.services.platform.options_policy import options_policy


def validate_runtime_and_model_options(
    *,
    engine: str,
    model: str | None,
    runtime_options: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_opts = options_policy.validate_runtime_options(runtime_options)
    engine_opts: dict[str, Any] = {}
    if model:
        validated = model_registry.validate_model(engine, model)
        engine_opts["model"] = validated["model"]
        if "model_reasoning_effort" in validated:
            engine_opts["model_reasoning_effort"] = validated["model_reasoning_effort"]
    return runtime_opts, engine_opts


def declared_execution_modes(skill: Any) -> set[str]:
    raw_modes = getattr(skill, "execution_modes", [ExecutionMode.AUTO.value]) or [
        ExecutionMode.AUTO.value
    ]
    modes: set[str] = set()
    for mode in raw_modes:
        if isinstance(mode, ExecutionMode):
            modes.add(mode.value)
        else:
            modes.add(str(mode))
    return modes


def ensure_skill_execution_mode_supported(
    *,
    skill_id: str,
    requested_mode: str,
    declared_modes: set[str],
) -> None:
    if requested_mode in declared_modes:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "code": "SKILL_EXECUTION_MODE_UNSUPPORTED",
            "message": (
                f"Skill '{skill_id}' does not support execution_mode "
                f"'{requested_mode}'"
            ),
            "declared_execution_modes": sorted(declared_modes),
            "requested_execution_mode": requested_mode,
        },
    )


def ensure_skill_engine_supported(
    *,
    skill_id: str,
    requested_engine: str,
    policy: SkillEnginePolicy,
) -> None:
    if requested_engine in policy.effective_engines:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "code": "SKILL_ENGINE_UNSUPPORTED",
            "message": f"Skill '{skill_id}' does not support engine '{requested_engine}'",
            "declared_engines": policy.declared_engines,
            "unsupported_engines": policy.unsupported_engines,
            "effective_engines": policy.effective_engines,
            "requested_engine": requested_engine,
        },
    )


def is_cache_enabled(runtime_options: dict[str, Any]) -> bool:
    execution_mode = runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
    if execution_mode != ExecutionMode.AUTO.value:
        return False
    return not bool(runtime_options.get("no_cache"))
