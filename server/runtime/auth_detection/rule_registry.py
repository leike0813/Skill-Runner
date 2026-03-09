from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from server.config import config
from server.config_registry import keys
from server.runtime.adapter.common.profile_loader import load_adapter_profile

from .rule_loader import RulePackLoadError
from .types import AuthDetectionRule

ALLOWED_OPERATORS = {"eq", "in", "regex", "contains", "gte"}


def _default_profile_paths() -> dict[str, Path]:
    root = Path(config.SYSTEM.ROOT)
    return {
        engine: root / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
        for engine in keys.ENGINE_KEYS
    }


@dataclass
class AuthDetectionRuleRegistry:
    """
    Validation-only registry for parser auth patterns.

    Runtime auth classification is parser-signal based and no longer uses this
    registry for evaluation.
    """

    profile_paths: dict[str, Path] = field(default_factory=_default_profile_paths)
    _loaded: bool = False
    _rules_by_engine: dict[str, list[AuthDetectionRule]] = field(default_factory=dict)

    def load(self) -> None:
        seen_rule_ids: set[str] = set()
        rules_by_engine: dict[str, list[AuthDetectionRule]] = {}
        for engine, profile_path in sorted(self.profile_paths.items()):
            profile = load_adapter_profile(engine, profile_path)
            parsed_rules: list[AuthDetectionRule] = []
            for rule in profile.parser_auth_patterns.rules:
                rule_id = rule.get("id")
                if not isinstance(rule_id, str) or not rule_id.strip():
                    raise RulePackLoadError(f"Invalid auth detection rule id: {rule_id!r}")
                if rule_id in seen_rule_ids:
                    raise RulePackLoadError(f"Duplicate auth detection rule id: {rule_id}")
                seen_rule_ids.add(rule_id)
                self._validate_match_ops(rule, engine=engine)
                parsed_rules.append(rule)
            rules_by_engine[engine] = sorted(
                parsed_rules,
                key=lambda item: int(item["priority"]),
                reverse=True,
            )
        self._rules_by_engine = rules_by_engine
        self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _validate_match_ops(self, rule: AuthDetectionRule, *, engine: str) -> None:
        match = rule.get("match", {})
        if not isinstance(match, dict):
            raise RulePackLoadError(f"Invalid auth detection match block for engine '{engine}'")
        for key in ("all", "any"):
            clauses = match.get(key)
            if clauses is None:
                continue
            if not isinstance(clauses, list):
                raise RulePackLoadError(
                    f"Invalid auth detection clauses '{key}' for rule '{rule.get('id')}'"
                )
            for clause in clauses:
                if not isinstance(clause, dict):
                    raise RulePackLoadError(
                        f"Invalid auth detection clause for rule '{rule.get('id')}'"
                    )
                op = clause.get("op")
                if op not in ALLOWED_OPERATORS:
                    raise RulePackLoadError(
                        f"Invalid auth detection operator '{op}' in rule '{rule.get('id')}'"
                    )
