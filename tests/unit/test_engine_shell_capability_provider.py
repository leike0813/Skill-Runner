from __future__ import annotations

from pathlib import Path

from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.services.ui.engine_shell_capability_provider import EngineShellCapabilityProvider


def test_engine_shell_capability_provider_uses_adapter_profile_ui_shell_metadata() -> None:
    provider = EngineShellCapabilityProvider()
    for engine in ("codex", "gemini", "opencode", "claude", "qwen"):
        capability = provider.get(engine)
        assert capability is not None
        profile = load_adapter_profile(
            engine,
            Path("server") / "engines" / engine / "adapter" / "adapter_profile.json",
        )
        assert capability.command_id == profile.ui_shell.command_id
        assert capability.label == profile.ui_shell.label
        assert capability.engine == engine
        assert capability.launch_args == tuple(profile.resolve_command_defaults(action="ui_shell"))
        assert capability.trust_bootstrap_parent == profile.ui_shell.trust_bootstrap_parent
        assert capability.sandbox_arg == profile.ui_shell.sandbox_arg
        assert (
            capability.retry_without_sandbox_on_early_exit
            == profile.ui_shell.retry_without_sandbox_on_early_exit
        )
