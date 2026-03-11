from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from server.models import SkillManifest
from server.services.skill.skill_asset_resolver import load_resolved_json, resolve_schema_asset

WARNING_OUTPUT_ARTIFACT_PATH_REWRITTEN = "OUTPUT_ARTIFACT_PATH_REWRITTEN"
WARNING_OUTPUT_ARTIFACT_MOVED_INSIDE_RUN_DIR = "OUTPUT_ARTIFACT_MOVED_INSIDE_RUN_DIR"
WARNING_OUTPUT_ARTIFACT_PATH_INVALID = "OUTPUT_ARTIFACT_PATH_INVALID"
WARNING_OUTPUT_ARTIFACT_PATH_MISSING = "OUTPUT_ARTIFACT_PATH_MISSING"


@dataclass(frozen=True)
class ArtifactResolutionResult:
    output_data: Dict[str, Any]
    artifacts: List[str]
    warnings: List[str]
    missing_required_fields: List[str]


@dataclass(frozen=True)
class _ArtifactField:
    name: str
    required: bool


def collect_run_artifacts(run_dir: Path) -> List[str]:
    result_path = run_dir / "result" / "result.json"
    if result_path.exists():
        payload = load_resolved_json(result_path)
        if isinstance(payload, dict):
            artifacts_obj = payload.get("artifacts")
            if isinstance(artifacts_obj, list):
                parsed = [
                    item.strip()
                    for item in artifacts_obj
                    if isinstance(item, str) and item.strip()
                ]
                return sorted(dict.fromkeys(parsed))

    artifacts: List[str] = []
    for path in run_dir.rglob("*"):
        if path.is_file() and path.relative_to(run_dir).as_posix().startswith("artifacts/"):
            artifacts.append(path.relative_to(run_dir).as_posix())
    return sorted(dict.fromkeys(artifacts))


def resolve_output_artifact_paths(
    *,
    skill: SkillManifest,
    run_dir: Path,
    output_data: Dict[str, Any],
) -> ArtifactResolutionResult:
    updated_output = dict(output_data)
    warnings: List[str] = []
    artifacts: List[str] = []
    missing_required_fields: List[str] = []
    normalized_run_dir = run_dir.resolve()

    for field in _load_output_artifact_fields(skill):
        raw_value = updated_output.get(field.name)
        if not isinstance(raw_value, str) or not raw_value.strip():
            if field.required:
                missing_required_fields.append(field.name)
            continue

        raw_path = raw_value.strip()
        try:
            source_path = _resolve_run_local_path(run_dir=run_dir, raw_path=raw_path)
        except ValueError:
            _append_unique_warning(warnings, WARNING_OUTPUT_ARTIFACT_PATH_INVALID)
            if field.required:
                missing_required_fields.append(field.name)
            continue

        if source_path is None or not source_path.exists() or not source_path.is_file():
            _append_unique_warning(warnings, WARNING_OUTPUT_ARTIFACT_PATH_MISSING)
            if field.required:
                missing_required_fields.append(field.name)
            continue

        resolved_source = source_path.resolve()
        if not resolved_source.is_relative_to(normalized_run_dir):
            target_path = _fallback_target_path(
                run_dir=run_dir,
                field_name=field.name,
                source_path=resolved_source,
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(resolved_source), str(target_path))
            resolved_source = target_path.resolve()
            _append_unique_warning(warnings, WARNING_OUTPUT_ARTIFACT_MOVED_INSIDE_RUN_DIR)

        rel_path = resolved_source.relative_to(normalized_run_dir).as_posix()
        if updated_output.get(field.name) != rel_path:
            updated_output[field.name] = rel_path
            _append_unique_warning(warnings, WARNING_OUTPUT_ARTIFACT_PATH_REWRITTEN)
        artifacts.append(rel_path)

    return ArtifactResolutionResult(
        output_data=updated_output,
        artifacts=sorted(dict.fromkeys(artifacts)),
        warnings=warnings,
        missing_required_fields=missing_required_fields,
    )


def _append_unique_warning(warnings: List[str], code: str) -> None:
    if code not in warnings:
        warnings.append(code)


def _load_output_artifact_fields(skill: SkillManifest) -> List[_ArtifactField]:
    schema = _load_output_schema(skill)
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    required_fields = {
        field.strip()
        for field in schema.get("required", [])
        if isinstance(field, str) and field.strip()
    }
    fields: List[_ArtifactField] = []
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(field_schema, dict):
            continue
        if str(field_schema.get("x-type") or "").strip().lower() not in {"artifact", "file"}:
            continue
        fields.append(_ArtifactField(name=field_name, required=field_name in required_fields))
    return fields


def _load_output_schema(skill: SkillManifest) -> Dict[str, Any] | None:
    return load_resolved_json(resolve_schema_asset(skill, "output").path)


def _resolve_run_local_path(*, run_dir: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()

    normalized_rel = _normalize_relative_path(raw_path)
    return (run_dir / normalized_rel).resolve()


def _normalize_relative_path(raw_path: str) -> str:
    normalized = PurePosixPath(raw_path.strip().replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("absolute path is not allowed")
    for part in normalized.parts:
        if part in {"", ".", ".."}:
            raise ValueError("invalid path")
    rel_path = normalized.as_posix()
    if not rel_path:
        raise ValueError("path is required")
    return rel_path


def _fallback_target_path(*, run_dir: Path, field_name: str, source_path: Path) -> Path:
    file_name = source_path.name or field_name
    return run_dir / "artifacts" / field_name / file_name
