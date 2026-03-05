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
    assert "deepseek" not in capabilities["cli_delegate"]["opencode"]


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


def test_strategy_service_opencode_conversation_methods_use_provider_scope() -> None:
    service = EngineAuthStrategyService()

    assert service.methods_for_conversation("opencode", "openai") == ("callback", "device_auth")
    assert service.methods_for_conversation("opencode", "deepseek") == ("api_key",)
    assert service.methods_for_conversation("opencode", None) == ()


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
