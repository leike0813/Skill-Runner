from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from server.models import RunStatus
from server.services.orchestration.run_workspace_layout import require_layout_from_record
from server.services.platform.async_compat import maybe_await

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkspaceFileBinding:
    input_key: str
    source_request_id: str
    source_path: str
    target_path: str


class WorkspaceFileBindingError(ValueError):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_workspace_file_bindings(runtime_options: dict[str, Any]) -> list[WorkspaceFileBinding]:
    workspace_obj = runtime_options.get("workspace") if isinstance(runtime_options, dict) else None
    if not isinstance(workspace_obj, dict):
        return []
    raw_bindings = workspace_obj.get("file_bindings")
    if raw_bindings is None:
        return []
    if not isinstance(raw_bindings, list):
        raise WorkspaceFileBindingError("runtime_options.workspace.file_bindings must be an array")

    bindings: list[WorkspaceFileBinding] = []
    seen_input_keys: set[str] = set()
    seen_targets: set[str] = set()
    for index, raw in enumerate(raw_bindings):
        if not isinstance(raw, dict):
            raise WorkspaceFileBindingError(
                f"runtime_options.workspace.file_bindings[{index}] must be an object"
            )
        values: dict[str, str] = {}
        for field in ("input_key", "source_request_id", "source_path", "target_path"):
            value = raw.get(field)
            if not isinstance(value, str) or not value.strip():
                raise WorkspaceFileBindingError(
                    f"runtime_options.workspace.file_bindings[{index}].{field} must be a non-empty string"
                )
            values[field] = value.strip()
        if values["input_key"] in seen_input_keys:
            raise WorkspaceFileBindingError(
                f"duplicate workspace file binding input_key: {values['input_key']}"
            )
        if values["target_path"] in seen_targets:
            raise WorkspaceFileBindingError(
                f"duplicate workspace file binding target_path: {values['target_path']}"
            )
        seen_input_keys.add(values["input_key"])
        seen_targets.add(values["target_path"])
        bindings.append(WorkspaceFileBinding(**values))
    return bindings


def binding_input_keys(bindings: Iterable[WorkspaceFileBinding]) -> set[str]:
    return {binding.input_key for binding in bindings}


def _normalize_relative_path(raw_value: str, *, label: str) -> str:
    raw = raw_value.strip().replace("\\", "/")
    if raw in {"", "."}:
        raise WorkspaceFileBindingError(f"{label} must be a non-empty relative file path")
    normalized = PurePosixPath(raw)
    if normalized.is_absolute():
        raise WorkspaceFileBindingError(f"{label} must be a relative file path")
    if normalized.as_posix() == ".":
        raise WorkspaceFileBindingError(f"{label} must be a non-empty relative file path")
    if any(part in {"", ".", ".."} for part in normalized.parts):
        raise WorkspaceFileBindingError(f"{label} must stay within its root")
    return normalized.as_posix()


def _resolve_child(root: Path, rel_path: str, *, label: str) -> Path:
    root_resolved = root.resolve()
    target = (root_resolved / rel_path).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise WorkspaceFileBindingError(f"{label} must stay within its root") from exc
    return target


def _same_physical_dir(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def _materialize_file(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_dir():
            raise WorkspaceFileBindingError(
                f"workspace file binding target already exists as a directory: {target}"
            )
        target.unlink()
    if os.name == "nt":
        shutil.copy2(source, target)
        return "copy"
    try:
        os.link(source, target)
        return "hardlink"
    except OSError as exc:
        logger.info(
            "workspace_file_binding_hardlink_fallback source=%s target=%s error=%s",
            source,
            target,
            exc,
        )
        shutil.copy2(source, target)
        return "copy"


async def materialize_workspace_file_bindings(
    *,
    bindings: list[WorkspaceFileBinding],
    inline_input: dict[str, Any],
    reuse_workspace_dir: Path,
    uploads_dir: Path,
    run_store_backend: Any,
) -> list[str]:
    materialized: list[str] = []
    if not bindings:
        return materialized

    for binding in bindings:
        declared_value = inline_input.get(binding.input_key)
        if declared_value != binding.target_path:
            raise WorkspaceFileBindingError(
                f"input.{binding.input_key} must exist and equal workspace file binding target_path"
            )

        source_record = await maybe_await(run_store_backend.get_request(binding.source_request_id))
        if not isinstance(source_record, dict):
            raise WorkspaceFileBindingError(
                f"workspace file binding source request not found: {binding.source_request_id}",
                status_code=404,
            )
        source_status = str(source_record.get("run_status") or source_record.get("status") or "").lower()
        if source_status != RunStatus.SUCCEEDED.value:
            raise WorkspaceFileBindingError(
                f"workspace file binding source request is not succeeded: {binding.source_request_id}",
                status_code=409,
            )
        try:
            source_layout = require_layout_from_record(source_record)
        except RuntimeError as exc:
            raise WorkspaceFileBindingError(
                f"workspace file binding source request has no workspace layout: {binding.source_request_id}",
                status_code=409,
            ) from exc
        if not _same_physical_dir(source_layout.workspace_dir, reuse_workspace_dir):
            raise WorkspaceFileBindingError(
                f"workspace file binding source request is outside the reused workspace: {binding.source_request_id}"
            )

        source_rel = _normalize_relative_path(binding.source_path, label="workspace file binding source_path")
        target_rel = _normalize_relative_path(binding.target_path, label="workspace file binding target_path")
        source_path = _resolve_child(reuse_workspace_dir, source_rel, label="workspace file binding source_path")
        target_path = _resolve_child(uploads_dir, target_rel, label="workspace file binding target_path")

        if not source_path.exists():
            raise WorkspaceFileBindingError(
                f"workspace file binding source file not found: {binding.source_path}",
                status_code=404,
            )
        if not source_path.is_file():
            raise WorkspaceFileBindingError(
                f"workspace file binding source_path must refer to a file: {binding.source_path}"
            )
        if target_path.exists() and target_path.is_dir():
            raise WorkspaceFileBindingError(
                f"workspace file binding target_path already exists as a directory: {binding.target_path}"
            )

        mode = _materialize_file(source_path, target_path)
        logger.info(
            "workspace_file_binding_materialized source_request_id=%s source_path=%s target_path=%s mode=%s",
            binding.source_request_id,
            binding.source_path,
            target_rel,
            mode,
        )
        materialized.append(target_rel)
    return materialized
