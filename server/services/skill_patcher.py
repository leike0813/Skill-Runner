from pathlib import Path
from typing import List
import logging

from ..models import ManifestArtifact


ARTIFACT_PATCH_MARKER = "# Runtime Output Overrides"
MODE_PATCH_MARKER = "# Automation Context"
COMPLETION_CONTRACT_MARKER = "## Runtime Completion Contract (Injected by Skill Runner)"

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

    def __init__(self) -> None:
        self._completion_contract_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "configs"
            / "completion_contract.md"
        )

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

    def _load_completion_contract(self) -> str:
        path = self._completion_contract_path
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"completion contract markdown is missing: {path}")
        try:
            content = path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            raise RuntimeError(f"completion contract markdown is unreadable: {path}") from exc
        if not content:
            raise RuntimeError(f"completion contract markdown is empty: {path}")
        if COMPLETION_CONTRACT_MARKER not in content:
            raise RuntimeError(
                f"completion contract markdown must contain marker: {COMPLETION_CONTRACT_MARKER}"
            )
        return content

    def generate_completion_contract_patch(self) -> str:
        return "\n" + self._load_completion_contract()

    def generate_mode_patch(self, execution_mode: str) -> str:
        """Generates mode-specific execution semantics patch."""
        mode = self._normalize_execution_mode(execution_mode)
        patch_lines = [
            "\n" + MODE_PATCH_MARKER,
            "You must ensure that the output is a schema-compatible JSON.",
        ]
        if mode == "interactive":
            patch_lines.append(
                "You MAY ask for user input when required."
            )
            patch_lines.append(
                "If you provide ask_user hints, use YAML (NOT JSON), wrapped by <ASK_USER_YAML>...</ASK_USER_YAML>."
            )
            patch_lines.append(
                "Example: <ASK_USER_YAML>\\nask_user:\\n  interaction_id: 2\\n  kind: open_text\\n  prompt: Please clarify ...\\n</ASK_USER_YAML>"
            )
            patch_lines.append(
                "Before real completion, you MUST NOT emit any __SKILL_DONE__ marker."
            )
            patch_lines.append(
                "Do NOT require user replies to follow a fixed JSON schema; user replies are free text."
            )
            patch_lines.append("Treat ask_user hints as optional UI hints only.")
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
        completion_contract_patch = self.generate_completion_contract_patch()
        mode_patch = self.generate_mode_patch(execution_mode)
        parts = [part for part in [artifact_patch, completion_contract_patch, mode_patch] if part]
        return "\n".join(parts)

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
    ) -> None:
        """
        Patches the SKILL.md file in the given skill directory to include 
        runtime artifact redirection instructions.
        """
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.exists():
            return

        try:
            current = skill_md_path.read_text(encoding="utf-8")
            updated = current
            artifact_patch = self.generate_artifact_patch(artifacts)
            completion_patch = self.generate_completion_contract_patch()
            mode_patch = self.generate_mode_patch(execution_mode)
            updated = self._append_patch_if_missing(
                updated,
                artifact_patch,
                ARTIFACT_PATCH_MARKER,
            )
            updated = self._append_patch_if_missing(
                updated,
                completion_patch,
                COMPLETION_CONTRACT_MARKER,
            )
            updated = self._append_patch_if_missing(
                updated,
                mode_patch,
                MODE_PATCH_MARKER,
            )
            if updated == current:
                return
            skill_md_path.write_text(updated, encoding="utf-8")
            logger.info("Patched SKILL.md definition at %s", skill_md_path)
        except Exception:
            logger.exception("Failed to patch SKILL.md")
            raise

skill_patcher = SkillPatcher()

logger = logging.getLogger(__name__)
