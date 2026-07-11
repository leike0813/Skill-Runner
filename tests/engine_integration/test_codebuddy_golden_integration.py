from __future__ import annotations

import pytest

from server.services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
from tests.common.protocol_golden_fixture_harness import execute_protocol_core_fixture
from tests.common.protocol_golden_fixture_loader import load_fixture
from tests.common.protocol_golden_fixture_normalizer import normalize_rasp_event


@pytest.mark.parametrize(
    ("fixture_id", "expected_event"),
    [
        ("codebuddy_success_protocol_synthetic", "agent.turn_complete"),
        ("codebuddy_exit_zero_auth_error_protocol_synthetic", "agent.turn_failed"),
        ("codebuddy_canceled_protocol_synthetic", "agent.turn_failed"),
        ("codebuddy_runtime_error_protocol_synthetic", "agent.turn_failed"),
        ("codebuddy_malformed_resync_protocol_synthetic", "agent.turn_complete"),
    ],
)
def test_codebuddy_synthetic_protocol_golden(fixture_id: str, expected_event: str, tmp_path) -> None:
    install_runtime_protocol_ports()
    rasp_events, _fcmp_events = execute_protocol_core_fixture(
        load_fixture(fixture_id),
        tmp_path=tmp_path,
    )
    assert expected_event in [normalize_rasp_event(event)["type"] for event in rasp_events]
