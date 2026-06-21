from __future__ import annotations

from dataclasses import dataclass

BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID = "BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID"
BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING = "BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING"


@dataclass(frozen=True)
class BundleAssemblyError(RuntimeError):
    code: str
    message: str
    path: str | None = None

    def __str__(self) -> str:
        if self.path:
            return f"{self.code}: {self.message} ({self.path})"
        return f"{self.code}: {self.message}"
