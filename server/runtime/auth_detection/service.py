from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .detector_registry import AuthDetectorRegistry, create_default_auth_detector_registry
from .rule_registry import AuthDetectionRuleRegistry
from .types import AuthDetectionEvidence, AuthDetectionResult


@dataclass
class AuthDetectionService:
    registry: AuthDetectionRuleRegistry = field(default_factory=AuthDetectionRuleRegistry)
    detector_registry: AuthDetectorRegistry = field(default_factory=create_default_auth_detector_registry)

    def preload(self) -> None:
        self.registry.ensure_loaded()

    def detect(
        self,
        *,
        engine: str,
        raw_stdout: str,
        raw_stderr: str,
        pty_output: str = "",
        runtime_parse_result: dict[str, Any] | None = None,
    ) -> AuthDetectionResult:
        detector = self.detector_registry.resolve(engine)
        if detector is None:
            return AuthDetectionResult(
                classification="unknown",
                subcategory=None,
                confidence="low",
                engine=engine,
                evidence_sources=["combined"],
                details={},
            )
        evidence = detector.build_evidence(
            engine=engine,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
            pty_output=pty_output,
            runtime_parse_result=runtime_parse_result,
        )
        matched = self.registry.evaluate(evidence)
        if matched is not None:
            return matched
        return AuthDetectionResult(
            classification="not_auth",
            subcategory=None,
            confidence="low",
            engine=engine,
            provider_id=evidence.provider_id,
            evidence_sources=list(evidence.evidence_sources),
            evidence_excerpt=evidence.combined_text[:240] if evidence.combined_text else None,
            details={"extracted": dict(evidence.extracted)},
        )


auth_detection_service = AuthDetectionService()
