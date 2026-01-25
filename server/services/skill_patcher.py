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
    def generate_patch_content(self, artifacts: List[ManifestArtifact]) -> str:
        """
        Generates the markdown content for artifact redirection.
        """
        if not artifacts:
            return ""

        patch_lines = [
            "\n", 
            "---", 
            "# Runtime Output Overrides", 
            "Please write the following outputs to these specific paths:",
            "IMPORTANT: Ignore any previous instructions regarding the file paths of these outputs."
        ]
        
        for artifact in artifacts:
             target_path = "{{ run_dir }}/artifacts/" + artifact.pattern
             patch_lines.append(f"- {artifact.role} ({artifact.pattern}) -> {target_path}")
        
        patch_lines.append("\nEnsure you do NOT write these files to the current directory, but specifically to the paths above.")
        
        # Add background automation context prompt
        patch_lines.append("\n# Automation Context")
        patch_lines.append("This skill is running in a background automation context. **You must NOT ask the user for clarification or decisions.**")
        patch_lines.append("If you encounter branching logic or uncertainty, you must proceed according to the \"default behavior protocol\"; if no default behavior protocol is found, you shall follow your judgment of the optimal course of action.")
        patch_lines.append("You must ensure that the output is a schema-compatible JSON.")
        
        return "\n".join(patch_lines)

    def patch_skill_md(self, skill_dir: Path, artifacts: List[ManifestArtifact]):
        """
        Patches the SKILL.md file in the given skill directory to include 
        runtime artifact redirection instructions.
        """
        patch_content = self.generate_patch_content(artifacts)
        if not patch_content:
            return

        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return

        try:
            with open(skill_md_path, "a") as f:
                f.write(patch_content)
            logger.info("Patched SKILL.md definition at %s", skill_md_path)
        except Exception as e:
            logger.exception("Failed to patch SKILL.md")

skill_patcher = SkillPatcher()

logger = logging.getLogger(__name__)
