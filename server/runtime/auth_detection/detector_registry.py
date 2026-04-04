from __future__ import annotations

from dataclasses import dataclass

from server.engines.codex.auth.detection import CodexAuthDetector
from server.engines.gemini.auth.detection import GeminiAuthDetector
from server.engines.iflow.auth.detection import IFlowAuthDetector
from server.engines.opencode.auth.detection import OpencodeAuthDetector
from server.engines.qwen.auth.detection import QwenAuthDetector

from .contracts import AuthDetector


@dataclass
class AuthDetectorRegistry:
    _detectors: dict[str, AuthDetector]

    def resolve(self, engine: str) -> AuthDetector | None:
        return self._detectors.get(engine.strip().lower())

    def register(self, engine: str, detector: AuthDetector) -> None:
        self._detectors[engine.strip().lower()] = detector

    def supported_engines(self) -> tuple[str, ...]:
        return tuple(sorted(self._detectors.keys()))


def create_default_auth_detector_registry() -> AuthDetectorRegistry:
    return AuthDetectorRegistry(
        _detectors={
            "codex": CodexAuthDetector(),
            "gemini": GeminiAuthDetector(),
            "iflow": IFlowAuthDetector(),
            "opencode": OpencodeAuthDetector(),
            "qwen": QwenAuthDetector(),
        }
    )
