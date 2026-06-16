from __future__ import annotations

import os
import stat

import pytest

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.services.platform.runtime_env_options import (
    RuntimeEnvSecretMissingError,
    RuntimeEnvSecretService,
    sanitize_runtime_options_env,
)


def test_sanitize_runtime_options_env_redacts_raw_values() -> None:
    sanitized, raw_env = sanitize_runtime_options_env({"env": {"FOO": "secret"}})

    assert sanitized == {"env": {"FOO": {"redacted": True}}}
    assert raw_env == {"FOO": "secret"}
    assert "secret" not in repr(sanitized)


def test_runtime_env_secret_service_round_trip_and_permissions(tmp_path) -> None:
    service = RuntimeEnvSecretService(tmp_path / "run_secrets")

    path = service.save(request_id="req-1", env={"FOO": "secret"})

    assert path is not None
    assert service.load(request_id="req-1") == {"FOO": "secret"}
    assert stat.S_IMODE(service.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    service.delete(request_id="req-1")
    with pytest.raises(RuntimeEnvSecretMissingError):
        service.load(request_id="req-1")


def test_runtime_env_overlay_is_run_local(monkeypatch) -> None:
    adapter = EngineExecutionAdapter()
    monkeypatch.delenv("LOCAL_ONLY", raising=False)

    first = adapter._apply_runtime_env_overlay(
        {"BASE": "1"},
        {"__runtime_env": {"LOCAL_ONLY": "yes"}},
    )
    second = adapter._apply_runtime_env_overlay({"BASE": "1"}, {})

    assert first == {"BASE": "1", "LOCAL_ONLY": "yes"}
    assert second == {"BASE": "1"}
    assert os.environ.get("LOCAL_ONLY") is None
