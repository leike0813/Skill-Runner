from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="iflow engine is deprecated and sealed off from active regression")

from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_sample


def test_iflow_auth_detection_matches_oauth_expired_fixture() -> None:
    sample = load_sample("iflow", "oauth_token_expired")
    adapter = IFlowExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=sample["stdout"].encode("utf-8"),
        stderr_raw=sample["stderr"].encode("utf-8"),
        pty_raw=sample["pty_output"].encode("utf-8"),
    )
    result = auth_detection_service.detect(
        engine="iflow",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "iflow_server_oauth2_required" in result.matched_rule_ids
    assert result.details.get("reason_code") == "IFLOW_SERVER_OAUTH2_REQUIRED"
