from __future__ import annotations

from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_sample


def test_iflow_auth_detection_matches_oauth_expired_fixture() -> None:
    sample = load_sample("iflow", "oauth_token_expired")
    result = auth_detection_service.detect(
        engine="iflow",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=None,
    )
    assert result.classification == "auth_required"
    assert result.subcategory == "oauth_reauth"
    assert result.confidence == "high"
    assert "iflow_server_oauth2_required" in result.matched_rule_ids
