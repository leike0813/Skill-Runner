from pathlib import Path
from typing import List
import logging
from ..models import ManifestArtifact

class SkillPatcher:
    """
    Modifies skill definitions at runtime to enforce environment constraints.
    
    Primary Use:
    - Injects artifact redirection instructions into `SKILL.md`.
    - Ensures agents write outputs to `artifacts/` instead of CWD.
    - Appends context prompts (e.g. "Do not ask questions").
    """
    def _normalize_execution_mode(self, execution_mode: str) -> str:
        mode = (execution_mode or "auto").strip().lower()
        if mode in {"auto", "interactive"}:
            return mode
        return "auto"

    def generate_artifact_patch(self, artifacts: List[ManifestArtifact]) -> str:
        """Generates mode-agnostic artifact redirection patch."""
        if not artifacts:
            return ""

        patch_lines = [
            "\n",
            "---",
            "# Runtime Output Overrides",
            "Please write the following outputs to these specific paths:",
            "IMPORTANT: Ignore any previous instructions regarding the file paths of these outputs.",
        ]
        for artifact in artifacts:
            target_path = "{{ run_dir }}/artifacts/" + artifact.pattern
            patch_lines.append(f"- {artifact.role} ({artifact.pattern}) -> {target_path}")
        patch_lines.append(
            "\nEnsure you do NOT write these files to the current directory, but specifically to the paths above."
        )
        return "\n".join(patch_lines)

    def generate_mode_patch(self, execution_mode: str) -> str:
        """Generates mode-specific execution semantics patch."""
        mode = self._normalize_execution_mode(execution_mode)
        patch_lines = [
            "\n# Automation Context",
            "You must ensure that the output is a schema-compatible JSON.",
        ]
        if mode == "interactive":
            patch_lines.append(
                "You MAY ask for user input when required, but you must emit a structured ask_user payload."
            )
            patch_lines.append(
                "The ask_user payload must include: interaction_id, kind, prompt."
            )
            patch_lines.append(
                "Supported kind values: choose_one, confirm, fill_fields, open_text, risk_ack."
            )
            patch_lines.append(
                "The ask_user payload MAY include: options, ui_hints, default_decision_policy."
            )
            patch_lines.append(
                "Do NOT require user replies to follow a fixed JSON schema; user replies are free text."
            )
        else:
            patch_lines.append(
                "This skill is running in a background automation context. **You must NOT ask the user for clarification or decisions.**"
            )
            patch_lines.append(
                "If you encounter branching logic or uncertainty, proceed using default behavior protocol or best judgment."
            )
        return "\n".join(patch_lines)

    def generate_patch_content(
        self,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
    ) -> str:
        artifact_patch = self.generate_artifact_patch(artifacts)
        mode_patch = self.generate_mode_patch(execution_mode)
        if artifact_patch:
            return f"{artifact_patch}\n{mode_patch}"
        return mode_patch

    def patch_skill_md(
        self,
        skill_dir: Path,
        artifacts: List[ManifestArtifact],
        execution_mode: str = "auto",
    ) -> None:
        """
        Patches the SKILL.md file in the given skill directory to include 
        runtime artifact redirection instructions.
        """
        patch_content = self.generate_patch_content(artifacts, execution_mode=execution_mode)
        if not patch_content:
            return

        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return

        try:
            with open(skill_md_path, "a", encoding="utf-8") as f:
                f.write(patch_content)
            logger.info("Patched SKILL.md definition at %s", skill_md_path)
        except Exception:
            logger.exception("Failed to patch SKILL.md")

skill_patcher = SkillPatcher()

logger = logging.getLogger(__name__)
