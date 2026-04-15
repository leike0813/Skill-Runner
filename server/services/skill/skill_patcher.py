from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

from pydantic import ValidationError

from server.models import ManifestArtifact
from .skill_patch_output_schema import (
    OUTPUT_CONTRACT_DETAILS_MARKER,
)
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

_PATCH_SKILL_MD_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    TypeError,
    ValueError,
)


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
            except (ValidationError, TypeError, ValueError):
                logger.warning("Ignore invalid manifest artifact payload: %r", item)
        return parsed

    def _load_template(self, template: SkillPatchTemplate) -> str:
        return load_template_content(template)

    def _render_artifact_patch(
        self,
        artifacts: List[ManifestArtifact],
        *,
        run_dir: Path | None = None,
    ) -> str:
        if not artifacts:
            return ""
        template = self._load_template(ARTIFACT_REDIRECTION_TEMPLATE)
        if "{artifact_lines}" not in template:
            raise RuntimeError(
                "patch_artifact_redirection.md must contain placeholder {artifact_lines}"
            )
        artifact_root = (
            f"{run_dir.as_posix()}/artifacts/" if isinstance(run_dir, Path) else "<cwd>/artifacts/"
        )
        lines: List[str] = []
        for artifact in artifacts:
            lines.append(
                f"- {artifact.role} ({artifact.pattern}) -> prefer writing the final deliverable under "
                f"`{artifact_root}` (nested folders allowed)"
            )
        return template.replace("{artifact_lines}", "\n".join(lines))

    def build_patch_plan(
        self,
        *,
        artifacts: List[ManifestArtifact],
        run_dir: Path | None = None,
        execution_mode: str = "auto",
        output_contract_details_markdown: str | None = None,
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
        artifact_patch = self._render_artifact_patch(artifacts, run_dir=run_dir)
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
        output_contract_details = (
            output_contract_details_markdown.strip()
            if isinstance(output_contract_details_markdown, str)
            else ""
        )
        if output_contract_details:
            plan.append(
                SkillPatchSection(
                    module="output_contract_details",
                    marker=OUTPUT_CONTRACT_DETAILS_MARKER,
                    content=output_contract_details,
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
        run_dir: Path | None = None,
        execution_mode: str = "auto",
        output_contract_details_markdown: str | None = None,
    ) -> str:
        plan = self.build_patch_plan(
            artifacts=self._coerce_artifacts(artifacts),
            run_dir=run_dir,
            execution_mode=execution_mode,
            output_contract_details_markdown=output_contract_details_markdown,
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
        run_dir: Path | None = None,
        execution_mode: str = "auto",
        output_contract_details_markdown: str | None = None,
    ) -> bool:
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return False
        parsed_artifacts = self._coerce_artifacts(artifacts)
        try:
            current = skill_md_path.read_text(encoding="utf-8")
            updated = current
            for section in self.build_patch_plan(
                artifacts=parsed_artifacts,
                run_dir=run_dir,
                execution_mode=execution_mode,
                output_contract_details_markdown=output_contract_details_markdown,
            ):
                updated = self._append_patch_if_missing(updated, section.content, section.marker)
            if updated == current:
                return False
            skill_md_path.write_text(updated, encoding="utf-8")
            logger.info("Patched SKILL.md definition at %s", skill_md_path)
            return True
        except _PATCH_SKILL_MD_EXCEPTIONS:
            logger.exception("Failed to patch SKILL.md")
            raise


skill_patcher = SkillPatcher()

logger = logging.getLogger(__name__)
