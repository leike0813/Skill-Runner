from __future__ import annotations

from server.services.engine_management.engine_model_catalog_lifecycle import (
    EngineModelCatalogLifecycle,
)


def test_codebuddy_is_not_a_runtime_probe_catalog() -> None:
    lifecycle = EngineModelCatalogLifecycle()

    assert "codebuddy" not in lifecycle.runtime_probe_engines()
    assert lifecycle.supports_engine("codebuddy") is False


def test_kilo_catalog_is_not_started_or_scheduled_when_not_confirmed(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.engine_status_cache_service.is_confirmed_present",
        lambda engine: False,
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.kilo_model_catalog.start",
        lambda: calls.append("start"),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.kilo_model_catalog.request_refresh_async",
        lambda *, reason: calls.append(reason),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.opencode_model_catalog.start",
        lambda: None,
    )

    lifecycle = EngineModelCatalogLifecycle()
    lifecycle.start()
    result = lifecycle.request_refresh_async("kilo", reason="manual")

    assert result is None
    assert calls == []


def test_kilo_catalog_starts_and_schedules_once_when_confirmed(monkeypatch) -> None:
    calls: list[str] = []
    marker = object()
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.engine_status_cache_service.is_confirmed_present",
        lambda engine: engine == "kilo",
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.kilo_model_catalog.start",
        lambda: calls.append("start"),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_model_catalog_lifecycle.kilo_model_catalog.request_refresh_async",
        lambda *, reason: calls.append(reason) or marker,
    )

    result = EngineModelCatalogLifecycle().request_refresh_async("kilo", reason="post_install")

    assert result is marker
    assert calls == ["start", "post_install"]
