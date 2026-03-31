from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.models import SkillManifest
from server.services.platform.schema_validator import schema_validator

WARNING_OUTPUT_RECOVERED_FROM_RESULT_FILE = "OUTPUT_RECOVERED_FROM_RESULT_FILE"
WARNING_OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES = "OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES"
WARNING_OUTPUT_RESULT_FILE_INVALID_JSON = "OUTPUT_RESULT_FILE_INVALID_JSON"
WARNING_OUTPUT_RESULT_FILE_SCHEMA_INVALID = "OUTPUT_RESULT_FILE_SCHEMA_INVALID"
WARNING_OUTPUT_RESULT_FILE_DECLARED_NOT_FOUND = "OUTPUT_RESULT_FILE_DECLARED_NOT_FOUND"


@dataclass(frozen=True)
class ResultFileFallbackWarning:
    code: str
    detail: str | None = None


@dataclass(frozen=True)
class ResultFileFallbackResolution:
    payload: dict[str, Any] | None = None
    selected_path: str | None = None
    warnings: list[ResultFileFallbackWarning] = field(default_factory=list)


def resolve_result_file_fallback(
    *,
    skill: SkillManifest,
    run_dir: Path,
) -> ResultFileFallbackResolution:
    target_name = _resolve_result_json_filename(skill)
    candidates = _collect_candidate_paths(run_dir=run_dir, file_name=target_name)
    if not candidates:
        detail = f"expected={target_name}"
        return ResultFileFallbackResolution(
            warnings=[ResultFileFallbackWarning(WARNING_OUTPUT_RESULT_FILE_DECLARED_NOT_FOUND, detail)],
        )

    warnings: list[ResultFileFallbackWarning] = []
    if len(candidates) > 1:
        selected_relpath = candidates[0].relative_to(run_dir).as_posix()
        warnings.append(
            ResultFileFallbackWarning(
                WARNING_OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES,
                f"expected={target_name} selected={selected_relpath} candidates={len(candidates)}",
            )
        )

    selected_path = candidates[0]
    relpath = selected_path.relative_to(run_dir).as_posix()
    try:
        payload = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        warnings.append(
            ResultFileFallbackWarning(
                WARNING_OUTPUT_RESULT_FILE_INVALID_JSON,
                f"path={relpath}",
            )
        )
        return ResultFileFallbackResolution(selected_path=relpath, warnings=warnings)

    if not isinstance(payload, dict):
        warnings.append(
            ResultFileFallbackWarning(
                WARNING_OUTPUT_RESULT_FILE_INVALID_JSON,
                f"path={relpath}",
            )
        )
        return ResultFileFallbackResolution(selected_path=relpath, warnings=warnings)

    schema_errors = schema_validator.validate_output(skill, payload)
    if schema_errors:
        warnings.append(
            ResultFileFallbackWarning(
                WARNING_OUTPUT_RESULT_FILE_SCHEMA_INVALID,
                f"path={relpath} errors={' | '.join(schema_errors)}",
            )
        )
        return ResultFileFallbackResolution(selected_path=relpath, warnings=warnings)

    warnings.append(
        ResultFileFallbackWarning(
            WARNING_OUTPUT_RECOVERED_FROM_RESULT_FILE,
            f"path={relpath}",
        )
    )
    return ResultFileFallbackResolution(
        payload=payload,
        selected_path=relpath,
        warnings=warnings,
    )


def _resolve_result_json_filename(skill: SkillManifest) -> str:
    default_name = f"{skill.id}.result.json"
    entrypoint = skill.entrypoint if isinstance(skill.entrypoint, dict) else {}
    raw_name = entrypoint.get("result_json_filename")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return default_name
    normalized = Path(raw_name.strip()).name.strip()
    return normalized or default_name


def _collect_candidate_paths(*, run_dir: Path, file_name: str) -> list[Path]:
    collected: list[Path] = []
    for path in run_dir.rglob(file_name):
        if not path.is_file():
            continue
        relpath = path.relative_to(run_dir).as_posix()
        if relpath.startswith("result/") or relpath.startswith(".audit/"):
            continue
        collected.append(path)
    return sorted(
        collected,
        key=lambda candidate: (
            -candidate.stat().st_mtime_ns,
            len(candidate.relative_to(run_dir).parts),
            candidate.relative_to(run_dir).as_posix(),
        ),
    )
