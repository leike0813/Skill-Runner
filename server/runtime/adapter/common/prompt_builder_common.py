from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from ....models import SkillManifest
from ....services.platform.schema_validator import schema_validator
from ..contracts import AdapterExecutionContext
from .profile_loader import AdapterProfile


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

    parameter_ctx = schema_validator.build_parameter_context(skill, input_data)
    if merge_input_if_no_parameter_schema and (not skill.schemas or "parameter" not in skill.schemas):
        parameter_ctx.update(input_data.get("input", {}))

    return input_ctx, parameter_ctx


def resolve_template_text(
    *,
    skill: SkillManifest,
    engine_key: str,
    default_template_path: Path | None,
    fallback_inline: str,
) -> str:
    if (
        skill.entrypoint
        and "prompts" in skill.entrypoint
        and engine_key in skill.entrypoint["prompts"]
        and isinstance(skill.entrypoint["prompts"][engine_key], str)
    ):
        return str(skill.entrypoint["prompts"][engine_key])

    if default_template_path is not None and default_template_path.exists():
        return default_template_path.read_text(encoding="utf-8")

    return fallback_inline


def render_template(template_text: str, **context: Any) -> str:
    return Template(template_text).render(**context)


def to_params_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


class ProfiledPromptBuilder:
    def __init__(self, *, adapter: Any, profile: AdapterProfile) -> None:
        self._adapter = adapter
        self._profile = profile

    def render(self, ctx: AdapterExecutionContext) -> str:
        skill = ctx.skill
        run_dir = ctx.run_dir
        input_data = ctx.input_data
        prompt_profile = self._profile.prompt_builder

        input_ctx, parameter_ctx = build_prompt_contexts(
            skill=skill,
            run_dir=run_dir,
            input_data=input_data,
            merge_input_if_no_parameter_schema=prompt_profile.merge_input_if_no_parameter_schema,
        )
        template_text = resolve_template_text(
            skill=skill,
            engine_key=prompt_profile.engine_key,
            default_template_path=self._profile.resolve_template_path(),
            fallback_inline=prompt_profile.fallback_inline,
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
        }
        if params_json is not None:
            context["params_json"] = params_json
        if prompt_profile.include_input_file_name:
            context["input_file"] = (run_dir / "input.json").name
        if prompt_profile.include_skill_dir:
            skill_dir = self._profile.skills_root_from(
                run_dir=run_dir,
                config_path=run_dir / self._profile.workspace_provisioner.workspace_subdir / "settings.json",
            ) / skill.id
            context["skill_dir"] = str(skill_dir)

        if prompt_profile.main_prompt_source == "parameter.prompt":
            default_prompt = prompt_profile.main_prompt_default_template.format(skill_id=skill.id)
            context["input_prompt"] = parameter_ctx.get("prompt", default_prompt)

        return render_template(template_text, **context)
