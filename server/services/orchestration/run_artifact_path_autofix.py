from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from server.models import SkillManifest

WARNING_OUTPUT_ARTIFACT_PATH_REPAIRED = "OUTPUT_ARTIFACT_PATH_REPAIRED"
WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS = (
    "OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS"
)
WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR = (
    "OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR"
)


@dataclass(frozen=True)
class ArtifactPathAutofixResult:
    output_data: Dict[str, Any]
    warnings: List[str]
    attempted: bool
    repaired_count: int


def collect_run_artifacts(run_dir: Path) -> List[str]:
    artifacts_dir = run_dir / "artifacts"
    artifacts: List[str] = []
    if artifacts_dir.exists():
        for path in artifacts_dir.rglob("*"):
            if path.is_file():
                artifacts.append(path.relative_to(run_dir).as_posix())
    artifacts.sort()
    return artifacts


def required_artifact_patterns(skill: SkillManifest) -> List[str]:
    if not skill.artifacts:
        return []
    return [artifact.pattern for artifact in skill.artifacts if artifact.required]


def missing_required_artifact_patterns(
    *,
    required_patterns: List[str],
    artifacts: List[str],
) -> List[str]:
    missing: List[str] = []
    for pattern in required_patterns:
        expected_path = f"artifacts/{pattern}"
        if expected_path not in artifacts:
            missing.append(pattern)
    return missing


def autofix_missing_artifact_paths(
    *,
    skill: SkillManifest,
    run_dir: Path,
    output_data: Dict[str, Any],
    missing_patterns: List[str],
) -> ArtifactPathAutofixResult:
    if not missing_patterns or not output_data:
        return ArtifactPathAutofixResult(
            output_data=dict(output_data),
            warnings=[],
            attempted=False,
            repaired_count=0,
        )

    field_mapping = _load_artifact_output_field_mapping(skill)
    normalized_run_dir = run_dir.resolve()
    updated_output = dict(output_data)
    warning_codes: List[str] = []
    attempted = False
    repaired_count = 0

    for pattern in missing_patterns:
        field_name = field_mapping.get(pattern)
        if field_name is None:
            continue
        raw_path = updated_output.get(field_name)
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        attempted = True
        source_path = _resolve_source_path_in_run(
            raw_path=raw_path.strip(),
            run_dir=run_dir,
        )
        if source_path is None:
            _append_unique_warning(
                warning_codes,
                WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR,
            )
            continue
        if not source_path.exists() or not source_path.is_file():
            source_path = _locate_candidate_by_filename_in_run(
                run_dir=run_dir,
                file_name=Path(raw_path.strip()).name,
            )
            if source_path is None:
                continue
        source_resolved = source_path.resolve()
        if not source_resolved.is_relative_to(normalized_run_dir):
            _append_unique_warning(
                warning_codes,
                WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR,
            )
            continue

        target_path = (run_dir / "artifacts" / pattern).resolve()
        if not target_path.is_relative_to(normalized_run_dir):
            _append_unique_warning(
                warning_codes,
                WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_OUTSIDE_RUN_DIR,
            )
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            _append_unique_warning(
                warning_codes,
                WARNING_OUTPUT_ARTIFACT_PATH_REPAIR_TARGET_EXISTS,
            )
            continue
        shutil.move(str(source_resolved), str(target_path))
        updated_output[field_name] = str(target_path)
        repaired_count += 1

    if repaired_count > 0:
        _append_unique_warning(
            warning_codes,
            WARNING_OUTPUT_ARTIFACT_PATH_REPAIRED,
        )

    return ArtifactPathAutofixResult(
        output_data=updated_output,
        warnings=warning_codes,
        attempted=attempted,
        repaired_count=repaired_count,
    )


def _append_unique_warning(warnings: List[str], code: str) -> None:
    if code not in warnings:
        warnings.append(code)


def _resolve_source_path_in_run(*, raw_path: str, run_dir: Path) -> Path | None:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = run_dir / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(run_dir.resolve()):
        return None
    return resolved


def _locate_candidate_by_filename_in_run(
    *,
    run_dir: Path,
    file_name: str,
) -> Path | None:
    if not file_name:
        return None
    matches = [path for path in run_dir.rglob(file_name) if path.is_file()]
    if len(matches) != 1:
        return None
    return matches[0].resolve()


def _load_artifact_output_field_mapping(skill: SkillManifest) -> Dict[str, str]:
    schema = _load_output_schema(skill)
    if not schema:
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    mapping: Dict[str, str] = {}
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(field_schema, dict):
            continue
        x_type = field_schema.get("x-type")
        if x_type not in {"artifact", "file"}:
            continue
        raw_pattern = field_schema.get("x-filename")
        if isinstance(raw_pattern, str) and raw_pattern.strip():
            pattern = raw_pattern.strip()
        else:
            pattern = field_name
        if pattern not in mapping:
            mapping[pattern] = field_name
    return mapping


def _load_output_schema(skill: SkillManifest) -> Dict[str, Any] | None:
    if not skill.path or not skill.schemas:
        return None
    output_schema_relpath = skill.schemas.get("output")
    if not isinstance(output_schema_relpath, str) or not output_schema_relpath.strip():
        return None
    schema_path = skill.path / output_schema_relpath
    if not schema_path.exists() or not schema_path.is_file():
        return None
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None

