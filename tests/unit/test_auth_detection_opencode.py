from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.runtime.auth_detection.service import auth_detection_service
from tests.unit.auth_detection_test_utils import load_manifest, load_sample


def _load_runtime_parse_result(sample_root: Path) -> dict:
    diagnostics_path = sample_root / "parser_diagnostics.1.jsonl"
    diagnostics = []
    if diagnostics_path.exists():
        for line in diagnostics_path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            data = payload.get("data", {})
            code = data.get("code")
            if isinstance(code, str):
                diagnostics.append(code)
    return {
        "parser": "fixture",
        "confidence": 0.2,
        "session_id": None,
        "assistant_messages": [],
        "raw_rows": [],
        "diagnostics": diagnostics,
        "structured_types": [],
    }


@pytest.mark.parametrize(
    ("sample_id", "subcategory", "confidence"),
    [
        ("google_api_key_missing", "api_key_missing", "high"),
        ("openrouter_missing_auth_header", "api_key_missing", "high"),
        ("minimax_login_fail_401", "api_key_missing", "high"),
        ("moonshot_invalid_authentication", "invalid_api_key", "high"),
        ("deepseek_invalid_api_key", "invalid_api_key", "high"),
        ("opencode_invalid_api_key", "invalid_api_key", "high"),
        ("zai_token_expired_or_incorrect", "auth_expired", "high"),
        ("iflowcn_unknown_step_finish_loop", "unknown_auth", "medium"),
    ],
)
def test_opencode_auth_detection_matches_fixture_matrix(
    sample_id: str,
    subcategory: str,
    confidence: str,
) -> None:
    sample = load_sample("opencode", sample_id)
    result = auth_detection_service.detect(
        engine="opencode",
        raw_stdout=sample["stdout"],
        raw_stderr=sample["stderr"],
        pty_output=sample["pty_output"],
        runtime_parse_result=_load_runtime_parse_result(sample["root"]),
    )
    assert result.classification == "auth_required"
    assert result.subcategory == subcategory
    assert result.confidence == confidence


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
            runtime_parse_result=_load_runtime_parse_result(sample["root"]),
        )
        assert result.classification == item["expected_classification"]
        assert result.subcategory == item["expected_subcategory"]
