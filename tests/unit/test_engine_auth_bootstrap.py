from pathlib import Path

from server.runtime.auth.driver_registry import AuthDriverRegistry
from server.services.orchestration.engine_auth_bootstrap import (
    AuthBootstrapBundle,
    build_engine_auth_bootstrap,
)


class _StubManager:
    pass


def test_engine_auth_bootstrap_builds_bundle(tmp_path: Path) -> None:
    manager = _StubManager()
    bundle = build_engine_auth_bootstrap(manager, agent_home=tmp_path / "agent_home")

    assert isinstance(bundle, AuthBootstrapBundle)
    assert isinstance(bundle.driver_registry, AuthDriverRegistry)
    assert "codex" in bundle.engine_auth_handlers
    assert "gemini" in bundle.engine_auth_handlers
    assert "iflow" in bundle.engine_auth_handlers
    assert "opencode" in bundle.engine_auth_handlers
    assert bundle.driver_registry.supports(
        transport="oauth_proxy",
        engine="codex",
        auth_method="callback",
    )
    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="iflow",
        auth_method="auth_code_or_url",
    )
    assert hasattr(manager, "_codex_oauth_proxy_flow")
    assert hasattr(manager, "_gemini_oauth_proxy_flow")
    assert hasattr(manager, "_openai_device_proxy_flow")
