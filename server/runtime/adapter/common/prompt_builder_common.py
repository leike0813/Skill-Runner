from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jinja2 import Template

from ....models import SkillManifest
from ....services.platform.schema_validator import schema_validator
from ....services.skill.skill_asset_resolver import resolve_schema_asset
from ..contracts import AdapterExecutionContext
from .profile_loader import AdapterProfile

GLOBAL_FIRST_ATTEMPT_PREFIX_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3] / "assets" / "templates" / "global_first_attempt_prefix.j2"
)


def _normalize_prompt_file_path(value: str, *, platform_name: str | None = None) -> str:
    target = platform_name or os.name
    if target == "nt":
        return value.replace("/", "\\")
    return value.replace("\\", "/")


def normalize_prompt_file_input_context(
    *,
    skill: SkillManifest,
    input_ctx: dict[str, Any],
    platform_name: str | None = None,
) -> dict[str, Any]:
    file_keys = schema_validator.get_input_keys_by_source(skill, "file")
    if not file_keys:
        return dict(input_ctx)
    normalized_ctx = dict(input_ctx)
    for key in file_keys:
        raw_value = normalized_ctx.get(key)
        if not isinstance(raw_value, str):
            continue
        normalized_ctx[key] = _normalize_prompt_file_path(raw_value, platform_name=platform_name)
    return normalized_ctx


def build_prompt_contexts(
    *,
    skill: SkillManifest,
    run_dir: Path,
    input_data: dict[str, Any],
    merge_input_if_no_parameter_schema: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    input_ctx, missing_required = schema_validator.build_input_context(skill, run_dir, input_data)
    if missing_required:
        raise ValueError(f"Missing required input files: {', '.join(missing_required)}")

    input_ctx = normalize_prompt_file_input_context(skill=skill, input_ctx=input_ctx)
    parameter_ctx = schema_validator.build_parameter_context(skill, input_data)
    if merge_input_if_no_parameter_schema and resolve_schema_asset(skill, "parameter").path is None:
        parameter_ctx.update(input_data.get("input", {}))

    return input_ctx, parameter_ctx


def resolve_template_text(
    *,
    skill: SkillManifest,
    engine_key: str,
    default_template_path: Path | None,
    fallback_inline: str,
) -> str:
    prompts_obj = skill.entrypoint.get("prompts") if skill.entrypoint else None
    if isinstance(prompts_obj, dict):
        engine_prompt = prompts_obj.get(engine_key)
        if isinstance(engine_prompt, str):
            return engine_prompt

        common_prompt = prompts_obj.get("common")
        if isinstance(common_prompt, str):
            return common_prompt

    if default_template_path is not None and default_template_path.exists():
        return default_template_path.read_text(encoding="utf-8")

    return fallback_inline


def render_template(template_text: str, **context: Any) -> str:
    return Template(template_text).render(**context)


def to_params_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _normalize_relative_prompt_dir(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return "."
    normalized = normalized.lstrip("/")
    if normalized.startswith("./"):
        return normalized.rstrip("/")
    return f"./{normalized}".rstrip("/")


def build_engine_prompt_context(profile: AdapterProfile) -> dict[str, str]:
    workspace_dir = _normalize_relative_prompt_dir(profile.attempt_workspace.workspace_subdir)
    skills_subdir = profile.attempt_workspace.skills_subdir.strip().replace("\\", "/").strip("/")
    skills_dir = workspace_dir if not skills_subdir else f"{workspace_dir}/{skills_subdir}"
    return {
        "engine_id": profile.engine,
        "engine_workspace_dir": workspace_dir,
        "engine_skills_dir": skills_dir,
    }


def build_prompt_render_context(
    *,
    ctx: AdapterExecutionContext,
    profile: AdapterProfile,
) -> dict[str, Any]:
    skill = ctx.skill
    run_dir = ctx.run_dir
    input_data = ctx.input_data
    prompt_profile = profile.prompt_builder

    input_ctx, parameter_ctx = build_prompt_contexts(
        skill=skill,
        run_dir=run_dir,
        input_data=input_data,
        merge_input_if_no_parameter_schema=prompt_profile.merge_input_if_no_parameter_schema,
    )

    params_json: str | None = None
    if prompt_profile.params_json_source == "input_data":
        params_json = to_params_json(input_data)
    elif prompt_profile.params_json_source == "combined_input_parameter":
        params_json = to_params_json({"input": input_ctx, "parameter": parameter_ctx})

    context: dict[str, Any] = {
        "skill": skill,
        "skill_id": skill.id,
        "input": input_ctx,
        "parameter": parameter_ctx,
        "run_dir": str(run_dir),
        **build_engine_prompt_context(profile),
    }
    if params_json is not None:
        context["params_json"] = params_json
    if prompt_profile.include_input_file_name:
        context["input_file"] = (run_dir / ".audit" / "request_input.json").name
    if prompt_profile.include_skill_dir:
        skill_dir = skill.path or (
            profile.skills_root_from(
                run_dir=run_dir,
                config_path=run_dir / profile.attempt_workspace.workspace_subdir / "settings.json",
            ) / skill.id
        )
        context["skill_dir"] = str(skill_dir)

    if prompt_profile.main_prompt_source == "parameter.prompt":
        default_prompt = prompt_profile.main_prompt_default_template.format(skill_id=skill.id)
        context["input_prompt"] = parameter_ctx.get("prompt", default_prompt)
    return context


def render_global_first_attempt_prefix(
    *,
    ctx: AdapterExecutionContext,
    profile: AdapterProfile,
) -> str:
    template_path = GLOBAL_FIRST_ATTEMPT_PREFIX_TEMPLATE_PATH
    if not template_path.exists():
        return ""
    template_text = template_path.read_text(encoding="utf-8")
    if not template_text.strip():
        return ""
    context = build_prompt_render_context(ctx=ctx, profile=profile)
    return render_template(template_text, **context)


class ProfiledPromptBuilder:
    def __init__(self, *, adapter: Any, profile: AdapterProfile) -> None:
        self._adapter = adapter
        self._profile = profile

    def render(self, ctx: AdapterExecutionContext) -> str:
        skill = ctx.skill
        prompt_profile = self._profile.prompt_builder
        template_text = resolve_template_text(
            skill=skill,
            engine_key=prompt_profile.engine_key,
            default_template_path=self._profile.resolve_template_path(),
            fallback_inline=prompt_profile.fallback_inline,
        )
        context = build_prompt_render_context(ctx=ctx, profile=self._profile)
        return render_template(template_text, **context)
