from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException  # type: ignore[import-not-found]

from server.models import ClientConversationMode, ExecutionMode
from server.services.engine_management.engine_policy import SkillEnginePolicy
from server.services.engine_management.model_registry import model_registry
from server.services.platform.options_policy import options_policy
from server.runtime.session.timeout import resolve_interactive_reply_timeout


@dataclass(frozen=True)
class EffectiveRuntimePolicy:
    requested_execution_mode: str
    effective_execution_mode: str
    conversation_mode: str
    interactive_auto_reply: bool
    interactive_reply_timeout_sec: int

    @property
    def requires_session_conversation(self) -> bool:
        return self.conversation_mode == ClientConversationMode.SESSION.value

    @property
    def effective_interactive_require_user_reply(self) -> bool:
        return (
            self.requires_session_conversation
            and self.effective_execution_mode == ExecutionMode.INTERACTIVE.value
        )


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


def resolve_conversation_mode(client_metadata: dict[str, Any] | None) -> str:
    if not isinstance(client_metadata, dict):
        return ClientConversationMode.SESSION.value
    raw_mode = client_metadata.get("conversation_mode")
    if isinstance(raw_mode, ClientConversationMode):
        return raw_mode.value
    if isinstance(raw_mode, str):
        normalized = raw_mode.strip()
        allowed = {
            ClientConversationMode.SESSION.value,
            ClientConversationMode.NON_SESSION.value,
        }
        if normalized in allowed:
            return normalized
    return ClientConversationMode.SESSION.value


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


def normalize_effective_runtime_policy(
    *,
    declared_modes: set[str],
    runtime_options: dict[str, Any],
    client_metadata: dict[str, Any] | None,
) -> EffectiveRuntimePolicy:
    requested_mode = str(runtime_options.get("execution_mode", ExecutionMode.AUTO.value))
    conversation_mode = resolve_conversation_mode(client_metadata)
    timeout_resolution = resolve_interactive_reply_timeout(runtime_options)
    interactive_auto_reply = bool(runtime_options.get("interactive_auto_reply", False))
    if conversation_mode == ClientConversationMode.NON_SESSION.value:
        if ExecutionMode.AUTO.value in declared_modes:
            effective_mode = ExecutionMode.AUTO.value
            effective_auto_reply = False
            effective_timeout = 0
        elif ExecutionMode.INTERACTIVE.value in declared_modes:
            effective_mode = ExecutionMode.INTERACTIVE.value
            effective_auto_reply = True
            effective_timeout = 0
        else:
            effective_mode = requested_mode
            effective_auto_reply = interactive_auto_reply
            effective_timeout = timeout_resolution.value
    else:
        effective_mode = requested_mode
        effective_auto_reply = interactive_auto_reply
        effective_timeout = timeout_resolution.value
    return EffectiveRuntimePolicy(
        requested_execution_mode=requested_mode,
        effective_execution_mode=effective_mode,
        conversation_mode=conversation_mode,
        interactive_auto_reply=effective_auto_reply,
        interactive_reply_timeout_sec=effective_timeout,
    )


def build_effective_runtime_options(
    *,
    runtime_options: dict[str, Any],
    policy: EffectiveRuntimePolicy,
) -> dict[str, Any]:
    effective = dict(runtime_options)
    effective["execution_mode"] = policy.effective_execution_mode
    effective["interactive_auto_reply"] = policy.interactive_auto_reply
    effective["interactive_reply_timeout_sec"] = policy.interactive_reply_timeout_sec
    return effective


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
