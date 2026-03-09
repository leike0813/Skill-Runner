from __future__ import annotations

from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_sample


def test_gemini_auth_detection_matches_missing_auth_method_fixture() -> None:
    sample = load_sample("gemini", "auth_method_not_configured")
    adapter = GeminiExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=sample["stdout"].encode("utf-8"),
        stderr_raw=sample["stderr"].encode("utf-8"),
        pty_raw=sample["pty_output"].encode("utf-8"),
    )
    result = auth_detection_service.detect(
        engine="gemini",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "gemini_auth_method_not_configured" in result.matched_rule_ids
    assert result.details.get("reason_code") == "GEMINI_AUTH_METHOD_NOT_CONFIGURED"


def test_gemini_auth_detection_matches_oauth_prompt_diagnostic() -> None:
    adapter = GeminiExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=b"Please visit the following URL to authorize the application.\n",
        stderr_raw=b"Enter the authorization code:\n",
        pty_raw=b"",
    )
    result = auth_detection_service.detect(
        engine="gemini",
        raw_stdout="Please visit the following URL to authorize the application.",
        raw_stderr="Enter the authorization code:",
        pty_output="",
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "gemini_oauth_code_prompt_detected" in result.matched_rule_ids
    assert result.details.get("reason_code") == "GEMINI_OAUTH_CODE_PROMPT_DETECTED"
