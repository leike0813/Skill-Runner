from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from server.config_registry.registry import config_registry
from server.models import ManifestArtifact
from .skill_patch_output_schema import (
    OUTPUT_SCHEMA_PATCH_MARKER,
    render_interactive_pending_contract_markdown,
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
INTERACTIVE_PENDING_CONTRACT_PLACEHOLDER = "{interactive_pending_contract_block}"

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
        content = load_template_content(template)
        if (
            template.module == SkillPatchModule.MODE_INTERACTIVE
            and INTERACTIVE_PENDING_CONTRACT_PLACEHOLDER in content
        ):
            content = content.replace(
                INTERACTIVE_PENDING_CONTRACT_PLACEHOLDER,
                self._render_interactive_pending_contract_block(),
            )
        return content

    def _ask_user_schema_contract_path(self) -> Path:
        candidates = config_registry.ask_user_schema_paths()
        matched = next((path for path in candidates if path.exists()), None)
        if matched is None:
            raise RuntimeError("ask_user schema contract not found in canonical path")
        return matched

    def _render_interactive_pending_contract_block(self) -> str:
        try:
            contract_path = self._ask_user_schema_contract_path()
            payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("ask_user schema contract payload must be an object")
        except (OSError, UnicodeDecodeError, yaml.YAMLError, RuntimeError):
            logger.warning("Failed to load ask_user schema contract for template rendering", exc_info=True)
        return render_interactive_pending_contract_markdown(include_final_example=True)

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
            lines.append(
                f"- {artifact.role} ({artifact.pattern}) -> prefer writing the final deliverable under "
                "`{{ run_dir }}/artifacts/` (nested folders allowed)"
            )
        return template.replace("{artifact_lines}", "\n".join(lines))

    def build_patch_plan(
        self,
        *,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
        output_schema_summary_markdown: str | None = None,
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
            output_schema_summary_markdown.strip()
            if isinstance(output_schema_summary_markdown, str)
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
        output_schema_summary_markdown: str | None = None,
    ) -> str:
        plan = self.build_patch_plan(
            artifacts=self._coerce_artifacts(artifacts),
            execution_mode=execution_mode,
            output_schema_summary_markdown=output_schema_summary_markdown,
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
        output_schema_summary_markdown: str | None = None,
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
                execution_mode=execution_mode,
                output_schema_summary_markdown=output_schema_summary_markdown,
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
