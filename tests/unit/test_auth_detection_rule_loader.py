from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.runtime.auth_detection.rule_loader import RulePackLoadError
from server.runtime.auth_detection.rule_registry import AuthDetectionRuleRegistry
from tests.unit.auth_detection_test_utils import PROJECT_ROOT


def test_auth_detection_rule_registry_loads_builtin_rule_packs() -> None:
    registry = AuthDetectionRuleRegistry()
    registry.load()
    assert "opencode" in registry._rules_by_engine
    assert "codex" in registry._rules_by_engine
    assert "iflow" in registry._rules_by_engine


def test_auth_detection_rule_registry_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_src = (
        PROJECT_ROOT
        / "server"
        / "contracts"
        / "schemas"
        / "auth_detection_rule_pack.schema.json"
    )
    schema_dir.joinpath("rule_pack.schema.json").write_text(
        schema_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    rule_dir = tmp_path / "rules"
    rule_dir.mkdir(parents=True, exist_ok=True)
    duplicate_payload = {
        "version": 1,
        "engine": "codex",
        "rules": [
            {
                "id": "duplicate-rule",
                "enabled": True,
                "priority": 100,
                "match": {"all": [{"field": "combined_text", "op": "contains", "value": "401"}]},
                "classify": {
                    "classification": "auth_required",
                    "subcategory": "api_key_missing",
                    "confidence": "high",
                },
            }
        ],
    }
    for name in ("codex.yaml", "gemini.yaml"):
        (rule_dir / name).write_text(
            json.dumps(duplicate_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    registry = AuthDetectionRuleRegistry(
        rule_dir=rule_dir,
        schema_path=schema_dir / "rule_pack.schema.json",
    )
    with pytest.raises(RulePackLoadError, match="Duplicate auth detection rule id"):
        registry.load()


def test_auth_detection_rule_registry_rejects_invalid_subcategory(tmp_path: Path) -> None:
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_src = (
        PROJECT_ROOT
        / "server"
        / "contracts"
        / "schemas"
        / "auth_detection_rule_pack.schema.json"
    )
    schema_dir.joinpath("rule_pack.schema.json").write_text(
        schema_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    rule_dir = tmp_path / "rules"
    rule_dir.mkdir(parents=True, exist_ok=True)
    (rule_dir / "codex.yaml").write_text(
        json.dumps(
            {
                "version": 1,
                "engine": "codex",
                "rules": [
                    {
                        "id": "bad-subcategory",
                        "enabled": True,
                        "priority": 100,
                        "match": {
                            "all": [
                                {
                                    "field": "combined_text",
                                    "op": "contains",
                                    "value": "401",
                                }
                            ]
                        },
                        "classify": {
                            "classification": "auth_required",
                            "subcategory": "bad_value",
                            "confidence": "high",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    registry = AuthDetectionRuleRegistry(
        rule_dir=rule_dir,
        schema_path=schema_dir / "rule_pack.schema.json",
    )
    with pytest.raises(RulePackLoadError, match="Invalid auth detection rule pack"):
        registry.load()


def test_backend_rule_packs_do_not_encode_interactive_url_or_code_prompts() -> None:
    rule_dir = PROJECT_ROOT / "server" / "engines" / "auth_detection"
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(rule_dir.glob("*.yaml"))
    ).lower()
    assert "visit this url" not in combined
    assert "authorization code" not in combined
    assert "one-time code" not in combined
