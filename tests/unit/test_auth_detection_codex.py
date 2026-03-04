from __future__ import annotations

from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_sample


def test_codex_auth_detection_matches_missing_bearer_fixture() -> None:
    sample = load_sample("codex", "openai_missing_bearer_401")
    result = auth_detection_service.detect(
        engine="codex",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=None,
    )
    assert result.classification == "auth_required"
    assert result.subcategory == "api_key_missing"
    assert result.confidence == "high"
    assert "codex_missing_bearer_401" in result.matched_rule_ids
