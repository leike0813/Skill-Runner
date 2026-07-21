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
    def audit_dir(self) -> Path:
        return self.workspace_dir / ".audit" / self.namespace

    @property
    def bundle_dir(self) -> Path:
        return self.workspace_dir / "bundle" / self.namespace

    @property
    def interaction_reply_files_dir(self) -> Path:
        return self.workspace_dir / "uploads" / ".interaction-replies" / self.namespace

    def bundle_path(self, *, debug: bool = False) -> Path:
        filename = "run_bundle_debug.zip" if debug else "run_bundle.zip"
        return self.bundle_dir / filename

    def bundle_manifest_path(self, *, debug: bool = False) -> Path:
        filename = "manifest_debug.json" if debug else "manifest.json"
        return self.bundle_dir / filename


def default_namespace_for_run(skill_id: str, index: int = 1) -> str:
    return f"{safe_segment(skill_id, 'skill')}.{max(1, int(index))}"


def layout_from_record(record: dict[str, Any]) -> RunWorkspaceLayout | None:
    run_id = str(record.get("run_id") or "").strip()
    workspace_id = str(record.get("workspace_id") or run_id).strip()
    namespace = str(record.get("workspace_namespace") or "").strip()
    workspace_dir_raw = record.get("workspace_dir")
    if not (
        workspace_id
        and namespace
        and isinstance(workspace_dir_raw, str)
        and workspace_dir_raw.strip()
    ):
        return None
    return RunWorkspaceLayout(
        workspace_id=workspace_id,
        workspace_dir=Path(workspace_dir_raw),
        namespace=namespace,
    )


def require_layout_from_record(record: dict[str, Any]) -> RunWorkspaceLayout:
    layout = layout_from_record(record)
    if layout is None:
        raise RuntimeError("Run workspace layout is unavailable")
    return layout
