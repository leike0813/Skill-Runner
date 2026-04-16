from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from server.runtime.auth_detection.rule_loader import RulePackLoadError
from server.runtime.auth_detection.rule_registry import AuthDetectionRuleRegistry
from tests.unit.auth_detection_test_utils import PROJECT_ROOT


def _write_profile(
    *,
    root: Path,
    engine: str,
    rule_id: str,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in ("bootstrap.json", "default.json", "enforced.json"):
        (root / name).write_text("{}", encoding="utf-8")
    profile_path = root / f"{engine}_adapter_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "engine": engine,
                "provider_contract": {
                    "multi_provider": engine in {"gemini", "opencode"},
                    "canonical_provider_id": None if engine in {"gemini", "opencode"} else "openai",
                },
                "prompt_builder": {
                    "skill_invoke_line_template": "${{ skill.id }}",
                    "body_prefix_extra_block": "",
                    "body_suffix_extra_block": "",
                },
                "session_codec": {
                    "strategy": "regex_extract",
                    "error_message": "missing",
                    "error_prefix": None,
                    "required_type": None,
                    "id_field": None,
                    "recursive_key": None,
                    "fallback_text_finder": None,
                    "json_lines_finder": None,
                    "regex_pattern": "session:([a-z0-9-]+)",
                },
                "attempt_workspace": {
                    "workspace_subdir": f".{engine}",
                    "skills_subdir": "skills",
                    "use_config_parent_as_workspace": False,
                    "unknown_fallback": False,
                },
                "command_defaults": {
                    "start": ["--json"],
                    "resume": ["resume", "--json"],
                    "ui_shell": ["ui", "--json"],
                },
                "structured_output": {
                    "mode": "noop",
                    "cli_schema_strategy": "noop",
                    "compat_schema_strategy": "noop",
                    "prompt_contract_strategy": "canonical_summary",
                    "payload_canonicalizer": "noop",
                },
                "ui_shell": {
                    "command_id": f"{engine}_ui_shell",
                    "label": f"{engine} ui shell",
                    "trust_bootstrap_parent": False,
                    "sandbox_arg": None,
                    "retry_without_sandbox_on_early_exit": False,
                    "sandbox_probe_strategy": "static_unsupported",
                    "sandbox_probe_message": None,
                    "auth_hint_strategy": "none",
                    "runtime_override_strategy": "none",
                    "config_assets": {
                        "default_path": None,
                        "enforced_path": None,
                        "settings_schema_path": None,
                        "target_relpath": None,
                    },
                },
                "config_assets": {
                    "bootstrap_path": str(root / "bootstrap.json"),
                    "default_path": str(root / "default.json"),
                    "enforced_path": str(root / "enforced.json"),
                    "settings_schema_path": None,
                    "skill_defaults_path": None,
                },
                "model_catalog": {
                    "mode": "runtime_probe",
                    "manifest_path": None,
                    "models_root": None,
                    "seed_path": None,
                },
                "cli_management": {
                    "package": f"pkg-{engine}",
                    "binary_candidates": [engine],
                    "credential_imports": [
                        {
                            "source": "auth.json",
                            "target_relpath": f".{engine}/auth.json",
                        }
                    ],
                    "credential_policy": {
                        "mode": "all_of_sources",
                        "sources": ["auth.json"],
                        "settings_validator": None,
                    },
                    "resume_probe": {
                        "help_hints": ["resume"],
                        "dynamic_args": [],
                    },
                    "layout": {
                        "extra_dirs": [f".{engine}"],
                        "bootstrap_target_relpath": f".{engine}/config.json",
                        "bootstrap_format": "json",
                        "normalize_strategy": None,
                    },
                },
                "parser_auth_patterns": {
                    "rules": [
                        {
                            "id": rule_id,
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
                        }
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return profile_path


def test_auth_detection_rule_registry_loads_builtin_adapter_profiles() -> None:
    registry = AuthDetectionRuleRegistry()
    registry.load()
    assert "opencode" in registry._rules_by_engine
    assert "codex" in registry._rules_by_engine
    assert "gemini" in registry._rules_by_engine
    assert "qwen" in registry._rules_by_engine
    assert "claude" in registry._rules_by_engine


def test_auth_detection_rule_registry_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    codex_profile = _write_profile(root=tmp_path / "codex", engine="codex", rule_id="duplicate-rule")
    gemini_profile = _write_profile(root=tmp_path / "gemini", engine="gemini", rule_id="duplicate-rule")
    registry = AuthDetectionRuleRegistry(
        profile_paths={
            "codex": codex_profile,
            "gemini": gemini_profile,
        }
    )
    with pytest.raises(RulePackLoadError, match="Duplicate auth detection rule id"):
        registry.load()


def test_runtime_auth_detection_no_longer_reads_legacy_yaml_rule_packs() -> None:
    assert not (PROJECT_ROOT / "server" / "engines" / "auth_detection").exists()


def test_runtime_chain_no_longer_uses_rule_based_detection_service() -> None:
    runtime_paths = [
        PROJECT_ROOT / "server" / "runtime" / "adapter" / "base_execution_adapter.py",
        PROJECT_ROOT
        / "server"
        / "services"
        / "orchestration"
        / "run_job_lifecycle_service.py",
    ]
    for path in runtime_paths:
        text = path.read_text(encoding="utf-8")
        assert "auth_detection_service.detect(" not in text


def test_auth_detection_evidence_must_be_declared_in_profiles_not_parser_core() -> None:
    parser_and_core_paths = [
        PROJECT_ROOT / "server" / "engines" / "codex" / "adapter" / "stream_parser.py",
        PROJECT_ROOT / "server" / "engines" / "gemini" / "adapter" / "stream_parser.py",
        PROJECT_ROOT / "server" / "engines" / "claude" / "adapter" / "stream_parser.py",
        PROJECT_ROOT / "server" / "engines" / "qwen" / "adapter" / "stream_parser.py",
        PROJECT_ROOT / "server" / "engines" / "opencode" / "adapter" / "stream_parser.py",
        PROJECT_ROOT / "server" / "runtime" / "adapter" / "common" / "parser_auth_signal_matcher.py",
        PROJECT_ROOT / "server" / "services" / "orchestration" / "run_job_lifecycle_service.py",
    ]
    hardcoded_markers = [
        "visit the following url to authorize the application",
        "enter the authorization code",
    ]
    for path in parser_and_core_paths:
        text = path.read_text(encoding="utf-8").lower()
        for marker in hardcoded_markers:
            assert marker not in text, f"unexpected hardcoded auth marker in {path}: {marker}"


def test_auth_detection_profiles_and_common_fallback_are_single_source() -> None:
    profile_paths = [
        PROJECT_ROOT / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
        for engine in ("codex", "gemini", "claude", "opencode", "qwen")
    ]
    for profile_path in profile_paths:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        rules = payload.get("parser_auth_patterns", {}).get("rules", [])
        assert isinstance(rules, list) and rules, f"missing parser_auth_patterns.rules in {profile_path}"
        for rule in rules:
            assert "classify" not in rule

    fallback_path = (
        PROJECT_ROOT
        / "server"
        / "engines"
        / "common"
        / "auth_detection"
        / "common_fallback_patterns.json"
    )
    fallback_schema_path = (
        PROJECT_ROOT
        / "server"
        / "contracts"
        / "schemas"
        / "auth_fallback_patterns.schema.json"
    )
    fallback_payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    fallback_schema = json.loads(fallback_schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=fallback_payload, schema=fallback_schema)


def test_common_fallback_must_not_duplicate_engine_high_patterns() -> None:
    """
    Guardrail:
    common fallback rules are low-confidence pre-warning evidence only.
    They must not be exact duplicates of engine-specific high-confidence rules.
    """
    engine_rules: list[tuple[str, tuple[tuple[str, str, str], ...]]] = []
    for engine in ("codex", "gemini", "claude", "opencode", "qwen"):
        profile_path = (
            PROJECT_ROOT / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
        )
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        rules = payload.get("parser_auth_patterns", {}).get("rules", [])
        for rule in rules:
            signature = _rule_match_signature(rule)
            engine_rules.append((str(rule.get("id")), signature))

    fallback_path = (
        PROJECT_ROOT
        / "server"
        / "engines"
        / "common"
        / "auth_detection"
        / "common_fallback_patterns.json"
    )
    fallback_payload = json.loads(fallback_path.read_text(encoding="utf-8"))
    duplicate_pairs: list[tuple[str, str]] = []
    for fallback_rule in fallback_payload.get("rules", []):
        fallback_sig = _rule_match_signature(fallback_rule)
        fallback_id = str(fallback_rule.get("id"))
        for engine_rule_id, engine_sig in engine_rules:
            if fallback_sig == engine_sig:
                duplicate_pairs.append((fallback_id, engine_rule_id))

    assert not duplicate_pairs, (
        "common fallback rule duplicates engine-specific high rule(s): "
        + ", ".join(f"{fallback}->{engine}" for fallback, engine in duplicate_pairs)
    )


def _rule_match_signature(rule: dict) -> tuple[tuple[str, str, str], ...]:
    match = rule.get("match", {})
    if not isinstance(match, dict):
        return tuple()
    parts: list[tuple[str, str, str]] = []
    for bucket in ("all", "any"):
        clauses = match.get(bucket, [])
        if not isinstance(clauses, list):
            continue
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            field = str(clause.get("field", ""))
            op = str(clause.get("op", ""))
            value = clause.get("value")
            value_norm = json.dumps(value, ensure_ascii=False, sort_keys=True)
            parts.append((bucket, field, f"{op}:{value_norm}"))
    return tuple(sorted(parts))
