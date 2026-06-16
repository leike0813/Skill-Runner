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
