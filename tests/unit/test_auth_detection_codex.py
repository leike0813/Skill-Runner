from __future__ import annotations

from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_sample


def test_codex_auth_detection_matches_missing_bearer_fixture() -> None:
    sample = load_sample("codex", "openai_missing_bearer_401")
    adapter = CodexExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=sample["stdout"].encode("utf-8"),
        stderr_raw=sample["stderr"].encode("utf-8"),
        pty_raw=sample["pty_output"].encode("utf-8"),
    )
    result = auth_detection_service.detect(
        engine="codex",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "codex_missing_bearer_401" in result.matched_rule_ids
    assert result.details.get("reason_code") == "CODEX_MISSING_BEARER_401"


def test_codex_auth_detection_matches_refresh_token_reauth_fixture() -> None:
    sample = load_sample("codex", "openai_refresh_token_reused_401")
    adapter = CodexExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=sample["stdout"].encode("utf-8"),
        stderr_raw=sample["stderr"].encode("utf-8"),
        pty_raw=sample["pty_output"].encode("utf-8"),
    )
    result = auth_detection_service.detect(
        engine="codex",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "codex_refresh_token_reauth_required" in result.matched_rule_ids
    assert result.details.get("reason_code") == "CODEX_REFRESH_TOKEN_REAUTH_REQUIRED"


def test_codex_auth_detection_matches_logged_out_access_token_fixture() -> None:
    sample = load_sample("codex", "openai_access_token_logged_out_401")
    adapter = CodexExecutionAdapter()
    runtime_parse_result = adapter.parse_runtime_stream(
        stdout_raw=sample["stdout"].encode("utf-8"),
        stderr_raw=sample["stderr"].encode("utf-8"),
        pty_raw=sample["pty_output"].encode("utf-8"),
    )
    result = auth_detection_service.detect(
        engine="codex",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=runtime_parse_result,
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == "high"
    assert "codex_access_token_reauth_required" in result.matched_rule_ids
    assert result.details.get("reason_code") == "CODEX_ACCESS_TOKEN_REAUTH_REQUIRED"
