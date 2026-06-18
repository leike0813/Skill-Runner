from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_segment(value: Any, fallback: str = "skill") -> str:
    normalized = str(value or "").strip()
    cleaned = _SAFE_SEGMENT_RE.sub("-", normalized).strip("-")
    return cleaned or fallback


def workspace_output_token(*, cache_key: str | None, result_path: str | None) -> str:
    payload = {
        "cache_key": cache_key or "",
        "result_path": result_path or "",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RunWorkspaceLayout:
    workspace_id: str
    workspace_dir: Path
    namespace: str

    @property
    def result_path(self) -> Path:
        return self.workspace_dir / "result" / self.namespace / "result.json"

    @property
    def input_manifest_path(self) -> Path:
        return self.workspace_dir / ".audit" / self.namespace / "input_manifest.json"

    @property
    def state_path(self) -> Path:
        return self.workspace_dir / ".state" / self.namespace / "state.json"

    @property
    def dispatch_path(self) -> Path:
        return self.workspace_dir / ".state" / self.namespace / "dispatch.json"

    @property
    def audit_dir(self) -> Path:
        return self.workspace_dir / ".audit" / self.namespace

    @property
    def bundle_dir(self) -> Path:
        return self.workspace_dir / "bundle" / self.namespace

    def bundle_path(self, *, debug: bool = False) -> Path:
        filename = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        return self.bundle_dir / filename

    def bundle_manifest_path(self, *, debug: bool = False) -> Path:
        filename = "manifest_debug.json" if debug else "manifest.json"
        return self.bundle_dir / filename


def default_namespace_for_run(skill_id: str, index: int = 1) -> str:
    return f"{safe_segment(skill_id, 'skill')}.{max(1, int(index))}"


def legacy_layout(*, run_id: str, run_dir: Path, skill_id: str) -> RunWorkspaceLayout:
    return RunWorkspaceLayout(
        workspace_id=run_id,
        workspace_dir=run_dir,
        namespace=default_namespace_for_run(skill_id, 1),
    )


def layout_from_record(record: dict[str, Any], fallback_run_dir: Path | None = None) -> RunWorkspaceLayout | None:
    run_id = str(record.get("run_id") or "").strip()
    skill_id = str(record.get("skill_id") or "skill")
    workspace_id = str(record.get("workspace_id") or run_id).strip()
    namespace = str(record.get("workspace_namespace") or "").strip()
    workspace_dir_raw = record.get("workspace_dir")
    has_layout_metadata = bool(namespace) or (
        isinstance(workspace_dir_raw, str) and bool(workspace_dir_raw.strip())
    )
    if not has_layout_metadata:
        return None
    workspace_dir = Path(str(workspace_dir_raw)) if isinstance(workspace_dir_raw, str) and workspace_dir_raw else None
    if workspace_dir is None:
        workspace_dir = fallback_run_dir
    if not workspace_id or workspace_dir is None:
        return None
    return RunWorkspaceLayout(
        workspace_id=workspace_id,
        workspace_dir=workspace_dir,
        namespace=namespace or default_namespace_for_run(skill_id, 1),
    )


def record_has_workspace_layout(record: dict[str, Any]) -> bool:
    namespace = str(record.get("workspace_namespace") or "").strip()
    workspace_dir_raw = record.get("workspace_dir")
    return bool(namespace) or (
        isinstance(workspace_dir_raw, str) and bool(workspace_dir_raw.strip())
    )


def resolve_legacy_workspace_dir(
    *,
    workspace_backend: Any | None,
    run_id: str,
) -> Path | None:
    if workspace_backend is None or not run_id:
        return None
    for method_name in ("get_workspace_dir", "get_legacy_run_dir", "get_run_dir"):
        method = getattr(workspace_backend, method_name, None)
        if not callable(method):
            continue
        try:
            candidate = method(run_id)
        except (OSError, RuntimeError, ValueError, TypeError):
            continue
        if candidate is None:
            continue
        path = candidate if isinstance(candidate, Path) else Path(str(candidate))
        if path.exists():
            return path
    return None


def resolve_workspace_dir_from_record(
    record: dict[str, Any],
    *,
    workspace_backend: Any | None = None,
    run_id: str | None = None,
    fallback_workspace_dir: Path | None = None,
) -> Path | None:
    layout = layout_from_record(record, None)
    if layout is not None:
        return layout.workspace_dir if layout.workspace_dir.exists() else None
    if record_has_workspace_layout(record):
        return None
    if fallback_workspace_dir is not None and fallback_workspace_dir.exists():
        return fallback_workspace_dir
    resolved_run_id = str(run_id or record.get("run_id") or "").strip()
    return resolve_legacy_workspace_dir(
        workspace_backend=workspace_backend,
        run_id=resolved_run_id,
    )
