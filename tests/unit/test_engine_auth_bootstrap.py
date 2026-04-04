from pathlib import Path

from server.runtime.auth.driver_registry import AuthDriverRegistry
from server.services.engine_management.engine_auth_bootstrap import (
    AuthBootstrapBundle,
    build_engine_auth_bootstrap,
)


class _StubManager:
    pass


def test_engine_auth_bootstrap_builds_bundle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "server.services.engine_management.engine_auth_bootstrap.detect_pywinpty_support",
        lambda: (True, None),
    )
    manager = _StubManager()
    bundle = build_engine_auth_bootstrap(manager, agent_home=tmp_path / "agent_home")

    assert isinstance(bundle, AuthBootstrapBundle)
    assert isinstance(bundle.driver_registry, AuthDriverRegistry)
    assert "codex" in bundle.engine_auth_handlers
    assert "gemini" in bundle.engine_auth_handlers
    assert "iflow" in bundle.engine_auth_handlers
    assert "opencode" in bundle.engine_auth_handlers
    assert "qwen" in bundle.engine_auth_handlers
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
    assert bundle.driver_registry.supports(
        transport="oauth_proxy",
        engine="opencode",
        auth_method="api_key",
        provider_id="deepseek",
    )
    assert bundle.driver_registry.supports(
        transport="oauth_proxy",
        engine="qwen",
        auth_method="auth_code_or_url",
        provider_id="qwen-oauth",
    )
    assert hasattr(manager, "_codex_oauth_proxy_flow")
    assert hasattr(manager, "_gemini_oauth_proxy_flow")
    assert hasattr(manager, "_openai_device_proxy_flow")


def test_engine_auth_bootstrap_disables_windows_cli_delegate_without_pywinpty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.services.engine_management.engine_auth_bootstrap.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_auth_bootstrap.detect_pywinpty_support",
        lambda: (False, "import_error:ModuleNotFoundError"),
    )
    manager = _StubManager()
    bundle = build_engine_auth_bootstrap(manager, agent_home=tmp_path / "agent_home")

    assert bundle.driver_registry.supports(
        transport="oauth_proxy",
        engine="iflow",
        auth_method="auth_code_or_url",
    )
    assert not bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="iflow",
        auth_method="auth_code_or_url",
    )
    assert not bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="gemini",
        auth_method="auth_code_or_url",
    )
    assert not bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="opencode",
        auth_method="callback",
        provider_id="openai",
    )
    assert not bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="qwen",
        auth_method="auth_code_or_url",
        provider_id="qwen-oauth",
    )
    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="codex",
        auth_method="auth_code_or_url",
    )


def test_engine_auth_bootstrap_keeps_windows_cli_delegate_with_pywinpty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "server.services.engine_management.engine_auth_bootstrap.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_auth_bootstrap.detect_pywinpty_support",
        lambda: (True, None),
    )
    manager = _StubManager()
    bundle = build_engine_auth_bootstrap(manager, agent_home=tmp_path / "agent_home")

    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="iflow",
        auth_method="auth_code_or_url",
    )
    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="gemini",
        auth_method="auth_code_or_url",
    )
    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="opencode",
        auth_method="callback",
        provider_id="openai",
    )
    assert bundle.driver_registry.supports(
        transport="cli_delegate",
        engine="qwen",
        auth_method="auth_code_or_url",
        provider_id="qwen-oauth",
    )
