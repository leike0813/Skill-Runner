from pathlib import Path


def test_engine_auth_flow_manager_avoids_engine_bootstrap_imports() -> None:
    source = Path("server/services/orchestration/engine_auth_flow_manager.py").read_text(encoding="utf-8")
    assert "from server.services.orchestration.engine_auth_bootstrap import build_engine_auth_bootstrap" in source
    assert "runtime_handler import" not in source
    assert "callbacks.local_callback_server" not in source
    assert "OpenAIDeviceProxyFlow(" not in source
