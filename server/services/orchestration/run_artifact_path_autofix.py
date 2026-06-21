from __future__ import annotations

import json
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
BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID = "BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID"
BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING = "BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING"
BUNDLE_ASSEMBLY_MANIFEST_JSON_INVALID = "BUNDLE_ASSEMBLY_MANIFEST_JSON_INVALID"
BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT = "BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT"
BUNDLE_ASSEMBLY_MANIFEST_VALUE_NOT_PATH = "BUNDLE_ASSEMBLY_MANIFEST_VALUE_NOT_PATH"
ARTIFACT_MANIFEST_ROLE = "artifact-manifest"


@dataclass(frozen=True)
class ArtifactResolutionResult:
    output_data: Dict[str, Any]
    artifacts: List[str]
    warnings: List[str]
    missing_required_fields: List[str]
    assembly_errors: List[str]


@dataclass(frozen=True)
class _ArtifactField:
    name: str
    required: bool
    role: str | None


def collect_run_artifacts(run_dir: Path, result_path: Path | None = None) -> List[str]:
    if result_path is None:
        raise RuntimeError("result_path is required")
    candidate_result_paths: list[Path] = [result_path]
    seen_result_paths: set[str] = set()
    for candidate_result_path in candidate_result_paths:
        candidate_key = candidate_result_path.as_posix()
        if candidate_key in seen_result_paths or not candidate_result_path.exists():
            continue
        seen_result_paths.add(candidate_key)
        payload = load_resolved_json(candidate_result_path)
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
    assembly_errors: List[str] = []
    normalized_run_dir = run_dir.resolve()

    for field in _load_output_artifact_fields(skill, output_data=updated_output):
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
        if field.role == ARTIFACT_MANIFEST_ROLE:
            manifest_result = _expand_artifact_manifest(
                run_dir=run_dir,
                manifest_path=resolved_source,
                field_name=field.name,
            )
            for warning_code in manifest_result.warnings:
                _append_unique_warning(warnings, warning_code)
            assembly_errors.extend(manifest_result.errors)
            artifacts.extend(manifest_result.artifacts)

    return ArtifactResolutionResult(
        output_data=updated_output,
        artifacts=sorted(dict.fromkeys(artifacts)),
        warnings=warnings,
        missing_required_fields=missing_required_fields,
        assembly_errors=assembly_errors,
    )


def _append_unique_warning(warnings: List[str], code: str) -> None:
    if code not in warnings:
        warnings.append(code)


def _load_output_artifact_fields(
    skill: SkillManifest,
    *,
    output_data: Dict[str, Any] | None = None,
) -> List[_ArtifactField]:
    schema = _load_output_schema(skill)
    if not isinstance(schema, dict):
        return []
    output_payload = output_data if isinstance(output_data, dict) else {}
    fields: List[_ArtifactField] = []
    _collect_output_artifact_fields(
        schema=schema,
        output_data=output_payload,
        fields=fields,
    )
    merged: dict[str, _ArtifactField] = {}
    for field in fields:
        existing = merged.get(field.name)
        if existing is None:
            merged[field.name] = field
            continue
        merged[field.name] = _ArtifactField(
            name=field.name,
            required=existing.required or field.required,
            role=existing.role or field.role,
        )
    return list(merged.values())


def _collect_output_artifact_fields(
    *,
    schema: Dict[str, Any],
    output_data: Dict[str, Any],
    fields: List[_ArtifactField],
) -> None:
    properties = schema.get("properties")
    required_fields = {
        field.strip()
        for field in schema.get("required", [])
        if isinstance(field, str) and field.strip()
    }
    if isinstance(properties, dict):
        for field_name, field_schema in properties.items():
            if not isinstance(field_name, str) or not isinstance(field_schema, dict):
                continue
            if str(field_schema.get("x-type") or "").strip().lower() not in {"artifact", "file"}:
                continue
            role_obj = field_schema.get("x-role")
            role = role_obj.strip() if isinstance(role_obj, str) and role_obj.strip() else None
            fields.append(
                _ArtifactField(
                    name=field_name,
                    required=field_name in required_fields,
                    role=role,
                )
            )

    for sub_schema in _schema_list(schema.get("allOf")):
        _collect_output_artifact_fields(
            schema=sub_schema,
            output_data=output_data,
            fields=fields,
        )

    for keyword in ("oneOf", "anyOf"):
        branch_schemas = _schema_list(schema.get(keyword))
        if not branch_schemas:
            continue
        matching = [
            branch_schema
            for branch_schema in branch_schemas
            if _schema_branch_matches_output(branch_schema, output_data)
        ]
        for branch_schema in matching or branch_schemas:
            _collect_output_artifact_fields(
                schema=branch_schema,
                output_data=output_data,
                fields=fields,
            )


def _schema_list(raw_value: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_value, list):
        return []
    return [item for item in raw_value if isinstance(item, dict)]


def _schema_branch_matches_output(
    schema: Dict[str, Any],
    output_data: Dict[str, Any],
) -> bool:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return True

    discriminators_seen = 0
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(field_schema, dict):
            continue
        if field_name not in output_data:
            continue
        field_value = output_data.get(field_name)
        if "const" in field_schema:
            discriminators_seen += 1
            if field_value != field_schema.get("const"):
                return False
        enum_value = field_schema.get("enum")
        if isinstance(enum_value, list):
            discriminators_seen += 1
            if field_value not in enum_value:
                return False

    if discriminators_seen > 0:
        return True

    for sub_schema in _schema_list(schema.get("allOf")):
        if not _schema_branch_matches_output(sub_schema, output_data):
            return False
    return True


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


@dataclass(frozen=True)
class _ManifestExpansionResult:
    artifacts: List[str]
    warnings: List[str]
    errors: List[str]


def _expand_artifact_manifest(
    *,
    run_dir: Path,
    manifest_path: Path,
    field_name: str,
) -> _ManifestExpansionResult:
    warnings: List[str] = []
    errors: List[str] = []
    artifacts: List[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        _append_unique_warning(warnings, BUNDLE_ASSEMBLY_MANIFEST_JSON_INVALID)
        errors.append(
            f"{BUNDLE_ASSEMBLY_MANIFEST_JSON_INVALID}: artifact manifest field "
            f"{field_name!r} is not readable JSON ({exc})"
        )
        return _ManifestExpansionResult(artifacts=artifacts, warnings=warnings, errors=errors)

    if not isinstance(manifest, dict):
        _append_unique_warning(warnings, BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT)
        errors.append(
            f"{BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT}: artifact manifest field "
            f"{field_name!r} must contain a flat JSON object"
        )
        return _ManifestExpansionResult(artifacts=artifacts, warnings=warnings, errors=errors)

    run_dir_resolved = run_dir.resolve()
    for manifest_key, raw_path in manifest.items():
        key_label = str(manifest_key)
        if isinstance(raw_path, (dict, list)):
            _append_unique_warning(warnings, BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT)
            errors.append(
                f"{BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT}: artifact manifest field "
                f"{field_name!r} entry {key_label!r} must not contain nested values"
            )
            continue
        if not isinstance(raw_path, str) or not raw_path.strip():
            _append_unique_warning(warnings, BUNDLE_ASSEMBLY_MANIFEST_VALUE_NOT_PATH)
            errors.append(
                f"{BUNDLE_ASSEMBLY_MANIFEST_VALUE_NOT_PATH}: artifact manifest field "
                f"{field_name!r} entry {key_label!r} must be a non-empty path string"
            )
            continue
        try:
            rel_path = _normalize_relative_path(raw_path)
        except ValueError as exc:
            _append_unique_warning(warnings, BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID)
            errors.append(
                f"{BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID}: artifact manifest field "
                f"{field_name!r} entry {key_label!r} has invalid path {raw_path!r} ({exc})"
            )
            continue

        artifact_path = (run_dir / rel_path).resolve()
        try:
            artifact_path.relative_to(run_dir_resolved)
        except ValueError:
            _append_unique_warning(warnings, BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID)
            errors.append(
                f"{BUNDLE_ASSEMBLY_ARTIFACT_PATH_INVALID}: artifact manifest field "
                f"{field_name!r} entry {key_label!r} escapes the workspace"
            )
            continue
        if not artifact_path.exists() or not artifact_path.is_file():
            _append_unique_warning(warnings, BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING)
            errors.append(
                f"{BUNDLE_ASSEMBLY_ARTIFACT_PATH_MISSING}: artifact manifest field "
                f"{field_name!r} entry {key_label!r} references missing file {rel_path!r}"
            )
            continue
        artifacts.append(rel_path)

    return _ManifestExpansionResult(
        artifacts=sorted(dict.fromkeys(artifacts)),
        warnings=warnings,
        errors=errors,
    )
