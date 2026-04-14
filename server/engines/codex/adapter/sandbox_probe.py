from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PARSE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)

CODEX_SANDBOX_DEPENDENCY_MISSING = "CODEX_SANDBOX_DEPENDENCY_MISSING"
CODEX_SANDBOX_RUNTIME_UNAVAILABLE = "CODEX_SANDBOX_RUNTIME_UNAVAILABLE"
CODEX_SANDBOX_DISABLED_BY_ENV = "CODEX_SANDBOX_DISABLED_BY_ENV"
CODEX_SANDBOX_PROBE_KIND = "bubblewrap_smoke"


@dataclass(frozen=True)
class CodexSandboxProbeResult:
    declared_enabled: bool
    available: bool
    status: str
    warning_code: str | None
    message: str
    dependencies: dict[str, bool]
    missing_dependencies: list[str]
    checked_at: str | None = None
    probe_kind: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "declared_enabled": self.declared_enabled,
            "available": self.available,
            "status": self.status,
            "warning_code": self.warning_code,
            "message": self.message,
            "dependencies": dict(self.dependencies),
            "missing_dependencies": list(self.missing_dependencies),
            "checked_at": self.checked_at,
            "probe_kind": self.probe_kind,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CodexSandboxProbeResult | None":
        if not isinstance(payload, dict):
            return None
        dependencies_raw = payload.get("dependencies")
        dependencies: dict[str, bool] = {}
        if isinstance(dependencies_raw, dict):
            for key, value in dependencies_raw.items():
                if isinstance(key, str):
                    dependencies[key] = bool(value)
        missing_raw = payload.get("missing_dependencies")
        missing_dependencies = [
            str(item).strip()
            for item in missing_raw
            if isinstance(item, str) and str(item).strip()
        ] if isinstance(missing_raw, list) else []
        return cls(
            declared_enabled=bool(payload.get("declared_enabled", False)),
            available=bool(payload.get("available", False)),
            status=str(payload.get("status") or "unknown").strip() or "unknown",
            warning_code=(
                str(payload.get("warning_code")).strip()
                if isinstance(payload.get("warning_code"), str)
                and str(payload.get("warning_code")).strip()
                else None
            ),
            message=str(payload.get("message") or "").strip(),
            dependencies=dependencies,
            missing_dependencies=missing_dependencies,
            checked_at=(
                str(payload.get("checked_at")).strip()
                if isinstance(payload.get("checked_at"), str)
                and str(payload.get("checked_at")).strip()
                else None
            ),
            probe_kind=(
                str(payload.get("probe_kind")).strip()
                if isinstance(payload.get("probe_kind"), str)
                and str(payload.get("probe_kind")).strip()
                else None
            ),
        )


def codex_sandbox_probe_sidecar_path(agent_home: Path) -> Path:
    return agent_home / ".codex" / "sandbox_probe.json"


def load_codex_sandbox_probe(agent_home: Path) -> CodexSandboxProbeResult | None:
    path = codex_sandbox_probe_sidecar_path(agent_home)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except _PARSE_EXCEPTIONS:
        return None
    if not isinstance(payload, dict):
        return None
    return CodexSandboxProbeResult.from_payload(payload)


def write_codex_sandbox_probe(*, agent_home: Path, probe: CodexSandboxProbeResult) -> Path:
    path = codex_sandbox_probe_sidecar_path(agent_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(probe.to_payload(), indent=2) + "\n", encoding="utf-8")
    return path
