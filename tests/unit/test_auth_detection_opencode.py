from __future__ import annotations

import pytest

from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_manifest, load_sample


def _load_runtime_parse_result(sample: dict[str, object]) -> dict[str, object]:
    adapter = OpencodeExecutionAdapter()
    return adapter.parse_runtime_stream(
        stdout_raw=str(sample["stdout"]).encode("utf-8"),
        stderr_raw=str(sample["stderr"]).encode("utf-8"),
        pty_raw=str(sample["pty_output"]).encode("utf-8"),
    )


@pytest.mark.parametrize(
    ("sample_id", "confidence"),
    [
        ("google_api_key_missing", "high"),
        ("openrouter_missing_auth_header", "high"),
        ("minimax_login_fail_401", "high"),
        ("moonshot_invalid_authentication", "high"),
        ("deepseek_invalid_api_key", "high"),
        ("opencode_invalid_api_key", "high"),
        ("zai_token_expired_or_incorrect", "high"),
        ("iflowcn_unknown_step_finish_loop", "low"),
    ],
)
def test_opencode_auth_detection_matches_fixture_matrix(
    sample_id: str,
    confidence: str,
) -> None:
    sample = load_sample("opencode", sample_id)
    result = auth_detection_service.detect(
        engine="opencode",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=_load_runtime_parse_result(sample),
    )
    assert result.classification == "auth_required"
    assert result.subcategory is None
    assert result.confidence == confidence
    assert isinstance(result.details.get("reason_code"), str)


def test_auth_detection_manifest_matrix_stays_in_sync() -> None:
    manifest = load_manifest()
    for item in manifest["samples"]:
        if item["engine"] != "opencode":
            continue
        sample = load_sample("opencode", item["sample_id"])
        result = auth_detection_service.detect(
            engine="opencode",
            raw_stdout=sample["stdout"],
            raw_stderr=sample["stderr"],
            pty_output=sample["pty_output"],
            runtime_parse_result=_load_runtime_parse_result(sample),
        )
        assert result.classification == item["expected_classification"]
        assert result.subcategory is None
