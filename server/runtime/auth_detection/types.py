from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict

AuthClassification = Literal["auth_required", "not_auth", "unknown"]
AuthSubcategory = Literal[
    "oauth_reauth",
    "api_key_missing",
    "invalid_api_key",
    "auth_expired",
    "unknown_auth",
]
AuthConfidence = Literal["high", "low"]
EvidenceSource = Literal[
    "stdout_text",
    "stderr_text",
    "pty_output",
    "structured_json",
    "structured_ndjson",
    "process_exit",
    "combined",
    "parser_signal",
]
RuleOperator = Literal["eq", "in", "regex", "contains", "gte"]


class RuleMatchClause(TypedDict):
    field: str
    op: RuleOperator
    value: Any


class RuleMatchDefinition(TypedDict, total=False):
    all: list[RuleMatchClause]
    any: list[RuleMatchClause]


class AuthDetectionRule(TypedDict):
    id: str
    enabled: bool
    priority: int
    match: RuleMatchDefinition


class AuthDetectionRulePack(TypedDict):
    rules: list[AuthDetectionRule]


@dataclass(slots=True)
class AuthDetectionEvidence:
    engine: str
    provider_id: str | None = None
    stdout_text: str = ""
    stderr_text: str = ""
    pty_output: str = ""
    combined_text: str = ""
    parser_diagnostics: list[str] = field(default_factory=list)
    structured_types: list[str] = field(default_factory=list)
    extracted: dict[str, Any] = field(default_factory=dict)
    evidence_sources: list[EvidenceSource] = field(default_factory=list)

    def as_mapping(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "provider_id": self.provider_id,
            "stdout_text": self.stdout_text,
            "stderr_text": self.stderr_text,
            "pty_output": self.pty_output,
            "combined_text": self.combined_text,
            "parser_diagnostics": list(self.parser_diagnostics),
            "structured_types": list(self.structured_types),
            "extracted": dict(self.extracted),
            "evidence_sources": list(self.evidence_sources),
        }


@dataclass(slots=True)
class AuthDetectionResult:
    classification: AuthClassification
    subcategory: AuthSubcategory | None
    confidence: AuthConfidence
    engine: str
    provider_id: str | None = None
    matched_rule_ids: list[str] = field(default_factory=list)
    evidence_sources: list[EvidenceSource] = field(default_factory=list)
    evidence_excerpt: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        return self.classification == "auth_required"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
