from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from server import main


@pytest.mark.asyncio
async def test_lifespan_awaits_opencode_model_refresh_when_enabled(monkeypatch):
    monkeypatch.setattr("server.main.setup_logging", lambda: None)
    monkeypatch.setattr(
        "server.main.get_runtime_profile",
        lambda: SimpleNamespace(ensure_directories=lambda: None),
    )

    ensure_layout = Mock()
    monkeypatch.setattr(
        "server.services.engine_management.agent_cli_manager.AgentCliManager.ensure_layout",
        lambda self: ensure_layout(),
    )

    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.refresh_all",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.start",
        Mock(),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.stop",
        Mock(),
    )
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.start",
        Mock(),
    )
    refresh_mock = AsyncMock()
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.refresh",
        refresh_mock,
    )
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.stop",
        Mock(),
    )
    monkeypatch.setattr("server.services.platform.cache_manager.cache_manager.start", Mock())
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.start", Mock())
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_cleanup_manager.start", Mock())
    monkeypatch.setattr("server.services.skill.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", Mock())
    monkeypatch.setattr(
        "server.services.orchestration.job_orchestrator.job_orchestrator.recover_incomplete_runs_on_startup",
        AsyncMock(),
    )
    monkeypatch.setattr("server.services.platform.process_supervisor.process_supervisor.start", Mock())
    monkeypatch.setattr(
        "server.services.platform.process_supervisor.process_supervisor.reap_orphan_leases_on_startup",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.services.platform.process_supervisor.process_supervisor.stop",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr("server.services.ui.ui_auth.validate_ui_basic_auth_config", lambda: None)
    monkeypatch.setattr("server.services.orchestration.runtime_protocol_ports.install_runtime_protocol_ports", lambda: None)
    monkeypatch.setattr(
        "server.services.orchestration.runtime_observability_ports.install_runtime_observability_ports",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.main.config",
        SimpleNamespace(SYSTEM=SimpleNamespace(ENGINE_MODELS_CATALOG_STARTUP_PROBE=True)),
    )

    async with main.lifespan(main.app):
        pass

    refresh_mock.assert_awaited_once_with(reason="startup")
