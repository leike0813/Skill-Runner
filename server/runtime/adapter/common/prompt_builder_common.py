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


RUN_EXECUTION_INSTRUCTIONS_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3] / "assets" / "templates" / "run_execution_instructions.md.j2"
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


def resolve_body_template_text(
    *,
    skill: SkillManifest,
    engine_key: str,
    body_default_template_path: Path | None,
    body_fallback_inline: str,
) -> str:
    prompts_obj = skill.entrypoint.get("prompts") if skill.entrypoint else None
    if isinstance(prompts_obj, dict):
        engine_prompt = prompts_obj.get(engine_key)
        if isinstance(engine_prompt, str):
            return engine_prompt

        common_prompt = prompts_obj.get("common")
        if isinstance(common_prompt, str):
            return common_prompt

    if body_default_template_path is not None and body_default_template_path.exists():
        return body_default_template_path.read_text(encoding="utf-8")

    return body_fallback_inline


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


def build_prompt_base_context(
    *,
    run_dir: Path,
    profile: AdapterProfile,
    skill: SkillManifest | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "run_dir": str(run_dir),
        **build_engine_prompt_context(profile),
    }
    if skill is not None:
        context["skill"] = skill
        context["skill_id"] = skill.id
    return context


def build_prompt_render_context(
    *,
    ctx: AdapterExecutionContext,
    profile: AdapterProfile,
    extra_context: dict[str, Any] | None = None,
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
        **build_prompt_base_context(run_dir=run_dir, profile=profile, skill=skill),
        "input": input_ctx,
        "parameter": parameter_ctx,
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

    if prompt_profile.body_prompt_source == "parameter.prompt":
        default_prompt = prompt_profile.body_prompt_fallback_template.format(skill_id=skill.id)
        context["input_prompt"] = parameter_ctx.get("prompt", default_prompt)
    if isinstance(extra_context, dict) and extra_context:
        context.update(extra_context)
    return context


def render_skill_invoke_line(
    *,
    ctx: AdapterExecutionContext,
    profile: AdapterProfile,
    extra_context: dict[str, Any] | None = None,
) -> str:
    context = build_prompt_base_context(run_dir=ctx.run_dir, profile=profile, skill=ctx.skill)
    if isinstance(extra_context, dict) and extra_context:
        context.update(extra_context)
    rendered = render_template(profile.prompt_builder.skill_invoke_line_template, **context).strip()
    if not rendered:
        raise RuntimeError(f"Prompt invoke line rendered empty for engine '{profile.engine}'")
    return rendered


def assemble_prompt(*, invoke_line: str, body_prompt: str) -> str:
    invoke = invoke_line.strip()
    if not invoke:
        raise RuntimeError("Prompt invoke line must not be empty")
    body = body_prompt.lstrip("\n")
    if not body.strip():
        return invoke
    return f"{invoke}\n{body}"


def render_run_execution_instructions(
    *,
    run_dir: Path,
    profile: AdapterProfile,
    skill: SkillManifest | None = None,
) -> str:
    template_path = RUN_EXECUTION_INSTRUCTIONS_TEMPLATE_PATH
    if not template_path.exists():
        raise RuntimeError(f"Run execution instructions template missing: {template_path}")
    template_text = template_path.read_text(encoding="utf-8")
    rendered = render_template(
        template_text,
        **build_prompt_base_context(run_dir=run_dir, profile=profile, skill=skill),
    ).strip()
    if not rendered:
        raise RuntimeError(f"Run execution instructions template rendered empty: {template_path}")
    return rendered


def resolve_run_instruction_filename(engine_name: str) -> str:
    normalized = (engine_name or "").strip().lower()
    if normalized == "claude":
        return "CLAUDE.md"
    if normalized == "gemini":
        return "GEMINI.md"
    return "AGENTS.md"


class ProfiledPromptBuilder:
    def __init__(self, *, adapter: Any, profile: AdapterProfile) -> None:
        self._adapter = adapter
        self._profile = profile

    def build_extra_context(self, ctx: AdapterExecutionContext) -> dict[str, Any]:
        _ = ctx
        return {}

    def render(self, ctx: AdapterExecutionContext) -> str:
        skill = ctx.skill
        prompt_profile = self._profile.prompt_builder
        extra_context = self.build_extra_context(ctx)
        template_text = resolve_body_template_text(
            skill=skill,
            engine_key=prompt_profile.engine_key,
            body_default_template_path=self._profile.resolve_body_template_path(),
            body_fallback_inline=prompt_profile.body_fallback_inline,
        )
        context = build_prompt_render_context(
            ctx=ctx,
            profile=self._profile,
            extra_context=extra_context,
        )
        body_prompt = render_template(template_text, **context)
        invoke_line = render_skill_invoke_line(
            ctx=ctx,
            profile=self._profile,
            extra_context=extra_context,
        )
        return assemble_prompt(invoke_line=invoke_line, body_prompt=body_prompt)
