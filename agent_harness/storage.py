from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import HarnessError


_HANDLE_RE = re.compile(r"^[0-9a-f]{8}$")
_ATTEMPT_META_RE = re.compile(r"^meta\.(\d+)\.json$")


@dataclass(frozen=True)
class AttemptPaths:
    attempt_number: int
    meta: Path
    stdin: Path
    stdout: Path
    stderr: Path
    pty_output: Path
    fs_before: Path
    fs_after: Path
    fs_diff: Path
    rasp_events: Path
    fcmp_events: Path
    parser_diagnostics: Path
    protocol_metrics: Path
    conformance_report: Path


def resolve_or_create_run_dir(run_root: Path, engine: str, selector: str | None) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    if not selector:
        run_id = f"{datetime.utcnow():%Y%m%dT%H%M%S}-{engine}-{uuid4().hex[:8]}"
        run_dir = run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    selector_trimmed = selector.strip()
    if not selector_trimmed:
        raise HarnessError("INVALID_RUN_SELECTOR", "run selector cannot be empty")

    direct = Path(selector_trimmed).expanduser()
    if direct.is_absolute():
        target = direct.resolve()
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        return target

    named = (run_root / selector_trimmed).resolve()
    if named.exists():
        return named

    if _HANDLE_RE.match(selector_trimmed.lower()):
        matches = [path for path in run_root.iterdir() if path.is_dir() and path.name.endswith(selector_trimmed)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            matches.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            return matches[0]
        raise HarnessError(
            "RUN_SELECTOR_NOT_FOUND",
            f'No run matched selector "{selector_trimmed}"',
            details={"selector": selector_trimmed, "run_root": str(run_root)},
        )

    named.mkdir(parents=True, exist_ok=True)
    return named


def resolve_next_attempt_paths(run_dir: Path) -> AttemptPaths:
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    highest = 0
    for path in audit_dir.iterdir():
        matched = _ATTEMPT_META_RE.match(path.name)
        if not matched:
            continue
        attempt = int(matched.group(1))
        highest = max(highest, attempt)
    attempt_number = highest + 1
    suffix = f".{attempt_number}"
    return AttemptPaths(
        attempt_number=attempt_number,
        meta=audit_dir / f"meta{suffix}.json",
        stdin=audit_dir / f"stdin{suffix}.log",
        stdout=audit_dir / f"stdout{suffix}.log",
        stderr=audit_dir / f"stderr{suffix}.log",
        pty_output=audit_dir / f"pty-output{suffix}.log",
        fs_before=audit_dir / f"fs-before{suffix}.json",
        fs_after=audit_dir / f"fs-after{suffix}.json",
        fs_diff=audit_dir / f"fs-diff{suffix}.json",
        rasp_events=audit_dir / f"events{suffix}.jsonl",
        fcmp_events=audit_dir / f"fcmp_events{suffix}.jsonl",
        parser_diagnostics=audit_dir / f"parser_diagnostics{suffix}.jsonl",
        protocol_metrics=audit_dir / f"protocol_metrics{suffix}.json",
        conformance_report=audit_dir / f"conformance_report{suffix}.json",
    )


def snapshot_filesystem(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ignored_prefixes = (
        ".audit/",
        "interactions/",
        ".codex/",
        ".gemini/",
        ".iflow/",
        ".opencode/",
    )
    ignored_files = {
        "opencode.json",
    }
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel.startswith(ignored_prefixes):
            continue
        if rel in ignored_files:
            continue
        content = path.read_bytes()
        rows.append(
            {
                "path": rel,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
        )
    return rows


def diff_snapshot(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    before_map = {str(row.get("path", "")): row for row in before}
    after_map = {str(row.get("path", "")): row for row in after}
    created: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []

    for path, row in after_map.items():
        if not path:
            continue
        old = before_map.get(path)
        if old is None:
            created.append(row)
            continue
        if old.get("sha256") != row.get("sha256") or old.get("size") != row.get("size"):
            modified.append(
                {
                    "path": path,
                    "before": {"size": old.get("size"), "sha256": old.get("sha256")},
                    "after": {"size": row.get("size"), "sha256": row.get("sha256")},
                }
            )

    for path, row in before_map.items():
        if path and path not in after_map:
            deleted.append(row)

    return {"created": created, "modified": modified, "deleted": deleted}


def handles_index_path(run_root: Path) -> Path:
    return run_root / "interactive-handles.json"


def load_handle_index(run_root: Path) -> dict[str, Any]:
    path = handles_index_path(run_root)
    if not path.exists():
        return {"handles": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"handles": {}}
    if not isinstance(payload, dict):
        return {"handles": {}}
    handles = payload.get("handles")
    if not isinstance(handles, dict):
        payload["handles"] = {}
    return payload


def save_handle_index(run_root: Path, payload: dict[str, Any]) -> Path:
    path = handles_index_path(run_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.utcnow().isoformat()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def assign_handle(
    run_root: Path,
    run_id: str,
    metadata: dict[str, Any],
    preferred_handle: str | None = None,
) -> str:
    index = load_handle_index(run_root)
    handles = index.setdefault("handles", {})
    if not isinstance(handles, dict):
        handles = {}
        index["handles"] = handles
    handle = ""
    if preferred_handle:
        normalized = preferred_handle.strip().lower()
        if _HANDLE_RE.match(normalized):
            handle = normalized
    if not handle:
        seed = run_id[-8:].lower()
        handle = seed if _HANDLE_RE.match(seed) else uuid4().hex[:8]
        while handle in handles:
            handle = uuid4().hex[:8]
    handles[handle] = metadata
    save_handle_index(run_root, index)
    return handle


def load_handle_metadata(run_root: Path, handle: str) -> dict[str, Any]:
    normalized = handle.strip().lower()
    if not _HANDLE_RE.match(normalized):
        raise HarnessError(
            "INVALID_HANDLE",
            f'Invalid handle "{handle}". Expected 8-char hex suffix.',
            details={"handle": handle},
        )
    index = load_handle_index(run_root)
    handles = index.get("handles")
    if not isinstance(handles, dict):
        raise HarnessError("HANDLE_INDEX_INVALID", "interactive handle index is invalid")
    record = handles.get(normalized)
    if not isinstance(record, dict):
        raise HarnessError(
            "HANDLE_NOT_FOUND",
            f'Handle "{handle}" was not found.',
            details={"handle": normalized, "index_path": str(handles_index_path(run_root))},
        )
    return {"handle": normalized, **record}
