from server.runtime.auth.driver_registry import AuthDriverRegistry


def test_auth_driver_registry_resolve_and_fallback():
    registry = AuthDriverRegistry()
    registry.register(
        transport="cli_delegate",
        engine="opencode",
        auth_method="callback",
        driver="default-driver",
    )
    key, driver = registry.resolve(
        transport="cli_delegate",
        engine="opencode",
        auth_method="callback",
        provider_id="openai",
    )
    assert key.transport == "cli_delegate"
    assert key.provider_id == "openai"
    assert driver == "default-driver"


def test_auth_driver_registry_missing_raises():
    registry = AuthDriverRegistry()
    try:
        registry.resolve(
            transport="oauth_proxy",
            engine="codex",
            auth_method="auth_code_or_url",
        )
    except KeyError as exc:
        assert "Unsupported auth driver combination" in str(exc)
    else:
        raise AssertionError("Expected KeyError for missing registration")
