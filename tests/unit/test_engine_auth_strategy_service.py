from __future__ import annotations

from pathlib import Path

import pytest

from server.services.engine_management.engine_auth_strategy_service import (
    EngineAuthStrategyLoadError,
    EngineAuthStrategyService,
)


def test_strategy_service_exposes_ui_capabilities_from_policy() -> None:
    service = EngineAuthStrategyService()

    capabilities = service.list_ui_capabilities()

    assert capabilities["oauth_proxy"]["codex"] == ["callback", "auth_code_or_url"]
    assert capabilities["oauth_proxy"]["opencode"]["deepseek"] == ["api_key"]
    assert capabilities["oauth_proxy"]["opencode"]["alibaba-coding-plan"] == ["api_key"]
    assert capabilities["oauth_proxy"]["opencode"]["alibaba-coding-plan-cn"] == ["api_key"]
    assert capabilities["oauth_proxy"]["qwen"]["qwen-oauth"] == ["auth_code_or_url"]
    assert capabilities["oauth_proxy"]["qwen"]["coding-plan-china"] == ["api_key"]
    assert capabilities["oauth_proxy"]["qwen"]["coding-plan-global"] == ["api_key"]
    assert "deepseek" not in capabilities["cli_delegate"]["opencode"]


def test_strategy_service_exposes_high_risk_capabilities_from_policy() -> None:
    service = EngineAuthStrategyService()

    high_risk = service.list_ui_high_risk_capabilities()

    assert high_risk["oauth_proxy"]["opencode"]["google"] == ["callback", "auth_code_or_url"]
    assert high_risk["cli_delegate"]["opencode"]["google"] == ["auth_code_or_url"]
    assert "deepseek" not in high_risk["oauth_proxy"]["opencode"]


def test_strategy_service_high_risk_helpers_resolve_runtime_and_conversation_methods() -> None:
    service = EngineAuthStrategyService()

    assert service.is_runtime_method_high_risk(
        engine="opencode",
        transport="oauth_proxy",
        provider_id="google",
        auth_method="callback",
    )
    assert service.is_runtime_method_high_risk(
        engine="opencode",
        transport="cli_delegate",
        provider_id="google",
        auth_method="auth_code_or_url",
    )
    assert not service.is_runtime_method_high_risk(
        engine="opencode",
        transport="oauth_proxy",
        provider_id="deepseek",
        auth_method="api_key",
    )
    assert service.is_conversation_method_high_risk(
        engine="opencode",
        provider_id="google",
        conversation_method="callback",
    )


def test_strategy_service_supports_start_requires_explicit_provider_for_opencode() -> None:
    service = EngineAuthStrategyService()

    assert service.supports_start(
        transport="oauth_proxy",
        engine="opencode",
        auth_method="api_key",
        provider_id="deepseek",
    )
    assert not service.supports_start(
        transport="oauth_proxy",
        engine="opencode",
        auth_method="api_key",
        provider_id=None,
    )
    assert service.supports_start(
        transport="oauth_proxy",
        engine="qwen",
        auth_method="auth_code_or_url",
        provider_id="qwen-oauth",
    )
    assert not service.supports_start(
        transport="oauth_proxy",
        engine="qwen",
        auth_method="auth_code_or_url",
        provider_id=None,
    )


def test_strategy_service_opencode_conversation_methods_use_provider_scope() -> None:
    service = EngineAuthStrategyService()

    assert service.methods_for_conversation("opencode", "openai") == ("callback", "device_auth", "import")
    assert service.methods_for_conversation("opencode", "deepseek") == ("api_key",)
    assert service.methods_for_conversation("opencode", "alibaba-coding-plan") == ("api_key",)
    assert service.methods_for_conversation("opencode", "alibaba-coding-plan-cn") == ("api_key",)
    assert service.methods_for_conversation("opencode", None) == ()


def test_strategy_service_qwen_conversation_methods_use_provider_scope() -> None:
    service = EngineAuthStrategyService()

    assert service.methods_for_conversation("qwen", "qwen-oauth") == ("auth_code_or_url",)
    assert service.methods_for_conversation("qwen", "coding-plan-china") == ("api_key",)
    assert service.methods_for_conversation("qwen", "coding-plan-global") == ("api_key",)
    assert service.methods_for_conversation("qwen", None) == ()


def test_strategy_service_runtime_session_behavior_defaults_and_qwen_override() -> None:
    service = EngineAuthStrategyService()

    default_behavior = service.runtime_session_behavior_for_transport(
        engine="codex",
        transport="oauth_proxy",
    )
    qwen_behavior = service.runtime_session_behavior_for_transport(
        engine="qwen",
        transport="oauth_proxy",
        provider_id="qwen-oauth",
    )

    assert default_behavior.input_required is True
    assert default_behavior.polling_start == "manual_submit"
    assert qwen_behavior.input_required is False
    assert qwen_behavior.polling_start == "immediate"


def test_strategy_service_raises_for_invalid_payload(tmp_path: Path) -> None:
    invalid_strategy = tmp_path / "engine_auth_strategy.yaml"
    invalid_strategy.write_text("version: 1\nengines: {}\n", encoding="utf-8")
    schema_path = Path("server") / "contracts" / "schemas" / "engine_auth_strategy.schema.json"
    assert schema_path.exists()
    service = EngineAuthStrategyService(
        strategy_path=invalid_strategy,
        schema_path=schema_path,
    )

    with pytest.raises(EngineAuthStrategyLoadError):
        service.list_ui_capabilities()
