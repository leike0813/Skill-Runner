from __future__ import annotations

from typing import Any

from server.runtime.adapter.common.prompt_builder_common import (
    ProfiledPromptBuilder,
    build_prompt_render_context,
    render_template,
    resolve_template_text,
)

from .sandbox_probe import load_claude_sandbox_probe


class ClaudePromptBuilder(ProfiledPromptBuilder):
    def render(self, ctx: Any) -> str:
        prompt_profile = self._profile.prompt_builder
        template_text = resolve_template_text(
            skill=ctx.skill,
            engine_key=prompt_profile.engine_key,
            default_template_path=self._profile.resolve_template_path(),
            fallback_inline=prompt_profile.fallback_inline,
        )
        context = build_prompt_render_context(ctx=ctx, profile=self._profile)
        probe = load_claude_sandbox_probe(self._adapter.agent_manager.profile.agent_home)
        if probe is not None:
            context["claude_sandbox_available"] = probe.available
            context["claude_sandbox_message"] = probe.message
            context["claude_sandbox_warning_code"] = probe.warning_code
        return render_template(template_text, **context)
