from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class SkillPatchModule(str, Enum):
    RUNTIME_ENFORCEMENT = "runtime_enforcement"
    ARTIFACT_REDIRECTION = "artifact_redirection"
    OUTPUT_FORMAT_CONTRACT = "output_format_contract"
    MODE_AUTO = "mode_auto"
    MODE_INTERACTIVE = "mode_interactive"


@dataclass(frozen=True)
class SkillPatchTemplate:
    module: SkillPatchModule
    filename: str
    marker: str


RUNTIME_ENFORCEMENT_TEMPLATE = SkillPatchTemplate(
    module=SkillPatchModule.RUNTIME_ENFORCEMENT,
    filename="patch_runtime_enforcement.md",
    marker="Runtime Enforcement (Injected by Skill Runner",
)
ARTIFACT_REDIRECTION_TEMPLATE = SkillPatchTemplate(
    module=SkillPatchModule.ARTIFACT_REDIRECTION,
    filename="patch_artifact_redirection.md",
    marker="# Runtime Output Overrides",
)
OUTPUT_FORMAT_CONTRACT_TEMPLATE = SkillPatchTemplate(
    module=SkillPatchModule.OUTPUT_FORMAT_CONTRACT,
    filename="patch_output_format_contract.md",
    marker="## Output Format Contract",
)
MODE_AUTO_TEMPLATE = SkillPatchTemplate(
    module=SkillPatchModule.MODE_AUTO,
    filename="patch_mode_auto.md",
    marker="## Execution Mode: AUTO (Non-Interactive)",
)
MODE_INTERACTIVE_TEMPLATE = SkillPatchTemplate(
    module=SkillPatchModule.MODE_INTERACTIVE,
    filename="patch_mode_interactive.md",
    marker="## Execution Mode: INTERACTIVE",
)


def template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "templates"


def template_map() -> Dict[SkillPatchModule, SkillPatchTemplate]:
    return {
        RUNTIME_ENFORCEMENT_TEMPLATE.module: RUNTIME_ENFORCEMENT_TEMPLATE,
        ARTIFACT_REDIRECTION_TEMPLATE.module: ARTIFACT_REDIRECTION_TEMPLATE,
        OUTPUT_FORMAT_CONTRACT_TEMPLATE.module: OUTPUT_FORMAT_CONTRACT_TEMPLATE,
        MODE_AUTO_TEMPLATE.module: MODE_AUTO_TEMPLATE,
        MODE_INTERACTIVE_TEMPLATE.module: MODE_INTERACTIVE_TEMPLATE,
    }


def load_template_content(template: SkillPatchTemplate) -> str:
    path = template_dir() / template.filename
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Skill patch template is missing: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError(f"Skill patch template is empty: {path}")
    return content
