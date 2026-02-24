from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..models import ManifestArtifact
from .skill_patch_output_schema import OUTPUT_SCHEMA_PATCH_MARKER, generate_output_schema_patch
from .skill_patch_templates import (
    ARTIFACT_REDIRECTION_TEMPLATE,
    MODE_AUTO_TEMPLATE,
    MODE_INTERACTIVE_TEMPLATE,
    OUTPUT_FORMAT_CONTRACT_TEMPLATE,
    RUNTIME_ENFORCEMENT_TEMPLATE,
    SkillPatchModule,
    SkillPatchTemplate,
    load_template_content,
)


ARTIFACT_PATCH_MARKER = ARTIFACT_REDIRECTION_TEMPLATE.marker
MODE_AUTO_PATCH_MARKER = MODE_AUTO_TEMPLATE.marker
MODE_INTERACTIVE_PATCH_MARKER = MODE_INTERACTIVE_TEMPLATE.marker
RUNTIME_ENFORCEMENT_MARKER = RUNTIME_ENFORCEMENT_TEMPLATE.marker
OUTPUT_FORMAT_CONTRACT_MARKER = OUTPUT_FORMAT_CONTRACT_TEMPLATE.marker


@dataclass(frozen=True)
class SkillPatchSection:
    module: str
    marker: str
    content: str


class SkillPatcher:
    """
    Modifies SKILL.md at runtime using modular template-based injection.
    """

    def _normalize_execution_mode(self, execution_mode: str) -> str:
        mode = (execution_mode or "auto").strip().lower()
        return mode if mode in {"auto", "interactive"} else "auto"

    def _coerce_artifacts(self, artifacts: Iterable[Any]) -> List[ManifestArtifact]:
        parsed: List[ManifestArtifact] = []
        for item in artifacts:
            try:
                parsed.append(
                    item if isinstance(item, ManifestArtifact) else ManifestArtifact.model_validate(item)
                )
            except Exception:
                logger.warning("Ignore invalid manifest artifact payload: %r", item)
        return parsed

    def _load_template(self, template: SkillPatchTemplate) -> str:
        return load_template_content(template)

    def _render_artifact_patch(self, artifacts: List[ManifestArtifact]) -> str:
        if not artifacts:
            return ""
        template = self._load_template(ARTIFACT_REDIRECTION_TEMPLATE)
        if "{artifact_lines}" not in template:
            raise RuntimeError(
                "patch_artifact_redirection.md must contain placeholder {artifact_lines}"
            )
        lines: List[str] = []
        for artifact in artifacts:
            target_path = "{{ run_dir }}/artifacts/" + artifact.pattern
            lines.append(f"- {artifact.role} ({artifact.pattern}) -> {target_path}")
        return template.replace("{artifact_lines}", "\n".join(lines))

    def load_output_schema(
        self,
        *,
        skill_path: Optional[Path],
        output_schema_relpath: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not skill_path or not output_schema_relpath:
            return None
        schema_path = skill_path / output_schema_relpath
        if not schema_path.exists() or not schema_path.is_file():
            logger.warning("Output schema file not found: %s", schema_path)
            return None
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to parse output schema: %s", schema_path, exc_info=True)
            return None
        if not isinstance(payload, dict):
            logger.warning("Output schema root is not an object: %s", schema_path)
            return None
        return payload

    def discover_output_schema(self, skill_dir: Path) -> Optional[Dict[str, Any]]:
        candidates: List[Path] = []
        runner_path = skill_dir / "assets" / "runner.json"
        if runner_path.exists() and runner_path.is_file():
            try:
                runner_obj = json.loads(runner_path.read_text(encoding="utf-8"))
                if isinstance(runner_obj, dict):
                    schemas_obj = runner_obj.get("schemas")
                    if isinstance(schemas_obj, dict):
                        output_rel = schemas_obj.get("output")
                        if isinstance(output_rel, str) and output_rel.strip():
                            candidates.append(skill_dir / output_rel.strip())
            except Exception:
                logger.warning("Failed to parse runner.json for output schema: %s", runner_path)
        candidates.extend(
            [
                skill_dir / "assets" / "output.schema.json",
                skill_dir / "output.schema.json",
            ]
        )
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            if not path.exists() or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to parse output schema: %s", path, exc_info=True)
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def build_patch_plan(
        self,
        *,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> List[SkillPatchSection]:
        mode = self._normalize_execution_mode(execution_mode)
        plan: List[SkillPatchSection] = []
        plan.append(
            SkillPatchSection(
                module=SkillPatchModule.RUNTIME_ENFORCEMENT.value,
                marker=RUNTIME_ENFORCEMENT_MARKER,
                content=self._load_template(RUNTIME_ENFORCEMENT_TEMPLATE),
            )
        )
        artifact_patch = self._render_artifact_patch(artifacts)
        if artifact_patch:
            plan.append(
                SkillPatchSection(
                    module=SkillPatchModule.ARTIFACT_REDIRECTION.value,
                    marker=ARTIFACT_PATCH_MARKER,
                    content=artifact_patch,
                )
            )
        plan.append(
            SkillPatchSection(
                module=SkillPatchModule.OUTPUT_FORMAT_CONTRACT.value,
                marker=OUTPUT_FORMAT_CONTRACT_MARKER,
                content=self._load_template(OUTPUT_FORMAT_CONTRACT_TEMPLATE),
            )
        )
        output_schema_patch = (
            generate_output_schema_patch(output_schema)
            if isinstance(output_schema, dict)
            else ""
        )
        if output_schema_patch:
            plan.append(
                SkillPatchSection(
                    module="output_schema_specification",
                    marker=OUTPUT_SCHEMA_PATCH_MARKER,
                    content=output_schema_patch,
                )
            )
        mode_template = MODE_INTERACTIVE_TEMPLATE if mode == "interactive" else MODE_AUTO_TEMPLATE
        plan.append(
            SkillPatchSection(
                module=mode_template.module.value,
                marker=mode_template.marker,
                content=self._load_template(mode_template),
            )
        )
        return plan

    def generate_patch_content(
        self,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        plan = self.build_patch_plan(
            artifacts=self._coerce_artifacts(artifacts),
            execution_mode=execution_mode,
            output_schema=output_schema,
        )
        return "\n\n".join(section.content.strip() for section in plan if section.content.strip())

    def _append_patch_if_missing(self, current: str, patch: str, marker: str) -> str:
        if not patch.strip():
            return current
        if marker in current:
            return current
        trimmed = current.rstrip()
        if trimmed:
            return f"{trimmed}\n\n{patch.strip()}\n"
        return patch.strip() + "\n"

    def patch_skill_md(
        self,
        skill_dir: Path,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> bool:
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return False
        parsed_artifacts = self._coerce_artifacts(artifacts)
        schema_payload = output_schema if isinstance(output_schema, dict) else self.discover_output_schema(skill_dir)
        try:
            current = skill_md_path.read_text(encoding="utf-8")
            updated = current
            for section in self.build_patch_plan(
                artifacts=parsed_artifacts,
                execution_mode=execution_mode,
                output_schema=schema_payload,
            ):
                updated = self._append_patch_if_missing(updated, section.content, section.marker)
            if updated == current:
                return False
            skill_md_path.write_text(updated, encoding="utf-8")
            logger.info("Patched SKILL.md definition at %s", skill_md_path)
            return True
        except Exception:
            logger.exception("Failed to patch SKILL.md")
            raise


skill_patcher = SkillPatcher()

logger = logging.getLogger(__name__)
