from __future__ import annotations

from typing import Any

from server.runtime.adapter.common.prompt_builder_common import (
    ProfiledPromptBuilder,
)

from .sandbox_probe import load_claude_sandbox_probe


class ClaudePromptBuilder(ProfiledPromptBuilder):
    def build_extra_context(self, ctx: Any) -> dict[str, Any]:
        probe = load_claude_sandbox_probe(self._adapter.agent_manager.profile.agent_home)
        context: dict[str, Any] = {}
        if probe is not None:
            context["claude_sandbox_available"] = probe.available
            context["claude_sandbox_message"] = probe.message
            context["claude_sandbox_warning_code"] = probe.warning_code
        return context
