from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

from server.config import config

from .rule_loader import RulePackLoadError, load_rule_pack, load_rule_pack_schema
from .types import AuthDetectionEvidence, AuthDetectionResult, AuthDetectionRule, AuthDetectionRulePack

ALLOWED_SUBCATEGORIES = {
    "oauth_reauth",
    "api_key_missing",
    "invalid_api_key",
    "auth_expired",
    "unknown_auth",
}


@dataclass
class AuthDetectionRuleRegistry:
    rule_dir: Path = field(
        default_factory=lambda: Path(config.SYSTEM.ROOT) / "server" / "assets" / "auth_detection"
    )
    schema_path: Path = field(
        default_factory=lambda: Path(config.SYSTEM.ROOT)
        / "server"
        / "assets"
        / "schemas"
        / "auth_detection"
        / "rule_pack.schema.json"
    )
    _loaded: bool = False
    _packs: dict[str, AuthDetectionRulePack] = field(default_factory=dict)
    _rules_by_engine: dict[str, list[AuthDetectionRule]] = field(default_factory=dict)

    def load(self) -> None:
        schema = load_rule_pack_schema(self.schema_path)
        packs: dict[str, AuthDetectionRulePack] = {}
        seen_rule_ids: set[str] = set()
        for pack_path in sorted(self.rule_dir.glob("*.yaml")):
            pack = load_rule_pack(pack_path, schema=schema)
            engine = str(pack["engine"])
            rules: list[AuthDetectionRule] = []
            for rule in pack["rules"]:
                if rule["id"] in seen_rule_ids:
                    raise RulePackLoadError(f"Duplicate auth detection rule id: {rule['id']}")
                seen_rule_ids.add(rule["id"])
                subcategory = rule["classify"]["subcategory"]
                if subcategory is not None and subcategory not in ALLOWED_SUBCATEGORIES:
                    raise RulePackLoadError(f"Invalid auth detection subcategory: {subcategory}")
                rules.append(rule)
            packs[engine] = {
                "version": int(pack["version"]),
                "engine": engine,
                "rules": sorted(rules, key=lambda item: int(item["priority"]), reverse=True),
            }
        self._packs = packs
        self._rules_by_engine = {engine: list(pack["rules"]) for engine, pack in packs.items()}
        self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def evaluate(self, evidence: AuthDetectionEvidence) -> AuthDetectionResult | None:
        self.ensure_loaded()
        rules = [*self._rules_by_engine.get("common", []), *self._rules_by_engine.get(evidence.engine, [])]
        if not rules:
            return None
        evidence_mapping = evidence.as_mapping()
        for rule in rules:
            if not rule.get("enabled", True):
                continue
            if self._matches_rule(rule, evidence_mapping):
                classify = rule["classify"]
                excerpt = self._build_excerpt(evidence_mapping)
                return AuthDetectionResult(
                    classification=classify["classification"],
                    subcategory=classify["subcategory"],
                    confidence=classify["confidence"],
                    engine=evidence.engine,
                    provider_id=evidence.provider_id,
                    matched_rule_ids=[rule["id"]],
                    evidence_sources=list(evidence.evidence_sources),
                    evidence_excerpt=excerpt,
                    details={"extracted": dict(evidence.extracted)},
                )
        return None

    def _matches_rule(self, rule: AuthDetectionRule, evidence: dict[str, Any]) -> bool:
        match = rule.get("match", {})
        all_clauses = match.get("all", [])
        any_clauses = match.get("any", [])
        if all_clauses and not all(
            self._matches_clause(dict(clause), evidence) for clause in all_clauses
        ):
            return False
        if any_clauses and not any(
            self._matches_clause(dict(clause), evidence) for clause in any_clauses
        ):
            return False
        return bool(all_clauses or any_clauses)

    def _matches_clause(self, clause: dict[str, Any], evidence: dict[str, Any]) -> bool:
        actual = self._resolve_field_value(evidence, str(clause["field"]))
        op = clause["op"]
        expected = clause.get("value")
        if op == "eq":
            return actual == expected
        if op == "in":
            return actual in expected if isinstance(expected, list) else False
        if op == "regex":
            if not isinstance(actual, str) or not isinstance(expected, str):
                return False
            return re.search(expected, actual, re.IGNORECASE | re.MULTILINE) is not None
        if op == "contains":
            if isinstance(actual, str) and isinstance(expected, str):
                return expected.lower() in actual.lower()
            if isinstance(actual, list):
                return expected in actual
            return False
        if op == "gte":
            if actual is None or expected is None:
                return False
            try:
                return float(actual) >= float(expected)
            except (TypeError, ValueError):
                return False
        raise RulePackLoadError(f"Invalid auth detection operator: {op}")

    def _resolve_field_value(self, evidence: dict[str, Any], field: str) -> Any:
        current: Any = evidence
        for part in field.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _build_excerpt(self, evidence: dict[str, Any]) -> str | None:
        extracted = evidence.get("extracted")
        if isinstance(extracted, dict):
            message = extracted.get("message")
            if isinstance(message, str) and message.strip():
                return message[:240]
        combined = evidence.get("combined_text")
        if isinstance(combined, str) and combined.strip():
            return combined.strip()[:240]
        return None
