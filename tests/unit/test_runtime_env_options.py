from __future__ import annotations

import os
import stat

import pytest

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.services.platform.runtime_preamble_options import (
    RuntimePreambleSecretMissingError,
    RuntimePreambleSecretService,
    redact_runtime_preamble_prompt,
    sanitize_runtime_options_preamble,
)
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


def test_sanitize_runtime_options_preamble_redacts_raw_value() -> None:
    sanitized, raw_preamble = sanitize_runtime_options_preamble(
        {"preamble_prompt": "  client note\r\nnext line  "}
    )

    descriptor = sanitized["preamble_prompt"]
    assert descriptor["redacted"] is True
    assert descriptor["length"] == len("client note\nnext line")
    assert raw_preamble == "client note\nnext line"
    assert "client note" not in repr(sanitized)


def test_sanitize_runtime_options_preamble_preserves_descriptor() -> None:
    descriptor = redact_runtime_preamble_prompt("client note")
    sanitized, raw_preamble = sanitize_runtime_options_preamble(
        {"preamble_prompt": descriptor}
    )

    assert sanitized["preamble_prompt"] == descriptor
    assert raw_preamble is None


def test_runtime_preamble_secret_service_round_trip_and_permissions(tmp_path) -> None:
    service = RuntimePreambleSecretService(tmp_path / "run_secrets")

    path = service.save(request_id="req-1", preamble_prompt="client note")

    assert path is not None
    assert service.load(request_id="req-1") == "client note"
    assert stat.S_IMODE(service.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    service.delete(request_id="req-1")
    assert service.load(request_id="req-1") is None


def test_runtime_preamble_secret_service_loads_only_when_descriptor_present(
    tmp_path,
) -> None:
    service = RuntimePreambleSecretService(tmp_path / "run_secrets")
    service.save(request_id="req-1", preamble_prompt="client note")

    descriptor = redact_runtime_preamble_prompt("client note")
    assert (
        service.load_for_runtime_options(
            request_id="req-1",
            runtime_options={"preamble_prompt": descriptor},
        )
        == "client note"
    )
    assert (
        service.load_for_runtime_options(
            request_id="req-1",
            runtime_options={"execution_mode": "auto"},
        )
        is None
    )


def test_runtime_preamble_secret_service_missing_descriptor_secret_raises(tmp_path) -> None:
    service = RuntimePreambleSecretService(tmp_path / "run_secrets")
    descriptor = redact_runtime_preamble_prompt("client note")

    with pytest.raises(RuntimePreambleSecretMissingError):
        service.load_for_runtime_options(
            request_id="req-1",
            runtime_options={"preamble_prompt": descriptor},
        )
