from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.models import ExecutionMode, RunLocalSkillSource, SkillManifest
from server.services.orchestration.run_skill_materialization_service import (
    run_folder_bootstrapper,
)
from server.services.skill.skill_registry import skill_registry


SUPPORTED_SKILLS = ("literature-digest", "literature-explainer")
SUPPORTED_VIEWS = ("injected", "full")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a virtual run directory for a builtin skill and preview the "
            "runtime-patched SKILL.md content without submitting a real run."
        )
    )
    parser.add_argument(
        "--skill",
        choices=(*SUPPORTED_SKILLS, "all"),
        nargs="+",
        default=["all"],
        help="Builtin skill(s) to materialize. Default: all supported builtin preview skills.",
    )
    parser.add_argument(
        "--engine",
        required=True,
        help="Engine name used for structured-output prompt translation, e.g. codex or claude.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=[item.value for item in ExecutionMode],
        default="interactive",
        help="Execution mode for the virtual run.",
    )
    parser.add_argument(
        "--view",
        choices=SUPPORTED_VIEWS,
        default="injected",
        help="Print only the injected block or the full patched SKILL.md.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to write the rendered preview.",
    )
    parser.add_argument(
        "--keep-run-dir",
        action="store_true",
        help="Keep the temporary run directory on disk and print its location.",
    )
    args = parser.parse_args()

    skill_ids = _resolve_skill_ids(args.skill)
    outputs: list[str] = []
    for index, skill_id in enumerate(skill_ids):
        skill = _load_skill(skill_id)
        _validate_engine(skill, args.engine)
        _validate_execution_mode(skill, args.execution_mode)

        run_dir = Path(tempfile.mkdtemp(prefix=f"skill_patch_preview_{skill.id}_"))
        try:
            ref = run_folder_bootstrapper.materialize_skill(
                skill=skill,
                run_dir=run_dir,
                engine_name=args.engine,
                execution_mode=args.execution_mode,
                source=RunLocalSkillSource.INSTALLED,
            )
            snapshot_skill_md = ref.snapshot_dir / "SKILL.md"
            original_skill_md = (skill.path or Path()) / "SKILL.md"
            rendered = snapshot_skill_md.read_text(encoding="utf-8")
            output_text = (
                _extract_injected_block(
                    original=original_skill_md.read_text(encoding="utf-8"),
                    rendered=rendered,
                )
                if args.view == "injected"
                else rendered
            )

            run_dir_note = str(run_dir) if args.keep_run_dir else f"{run_dir} (temporary; deleted after exit)"
            header = [
                f"# Skill Patch Preview",
                f"",
                f"- skill: `{skill.id}`",
                f"- engine: `{args.engine}`",
                f"- execution_mode: `{args.execution_mode}`",
                f"- run_dir: `{run_dir_note}`",
                f"- snapshot_skill_md: `{snapshot_skill_md}`",
                f"",
            ]
            outputs.append("\n".join(header) + output_text)

            if args.keep_run_dir:
                print(f"Kept run directory for {skill.id}: {run_dir}", file=sys.stderr)
            else:
                shutil.rmtree(run_dir, ignore_errors=True)
        except Exception:
            if not args.keep_run_dir:
                shutil.rmtree(run_dir, ignore_errors=True)
            raise

        if index < len(skill_ids) - 1:
            outputs.append("\n\n" + ("=" * 80) + "\n\n")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("".join(outputs), encoding="utf-8")
        print(f"Wrote preview to {args.output}")
    else:
        final_output = "".join(outputs)
        sys.stdout.write(final_output)
        if not final_output.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _load_skill(skill_id: str) -> SkillManifest:
    skill = skill_registry.get_skill(skill_id)
    if skill is None or skill.path is None:
        raise RuntimeError(f"Builtin skill not found or missing path: {skill_id}")
    return skill


def _resolve_skill_ids(raw_skills: list[str]) -> list[str]:
    values = [item.strip() for item in raw_skills if isinstance(item, str) and item.strip()]
    if not values or "all" in values:
        return list(SUPPORTED_SKILLS)
    return values


def _validate_engine(skill: SkillManifest, engine_name: str) -> None:
    normalized = (engine_name or "").strip().lower()
    allowed = {item.strip().lower() for item in (skill.effective_engines or skill.engines or []) if item}
    if allowed and normalized not in allowed:
        raise RuntimeError(
            f"Skill '{skill.id}' does not declare engine '{engine_name}'. Allowed: {sorted(allowed)}"
        )


def _validate_execution_mode(skill: SkillManifest, execution_mode: str) -> None:
    normalized = (execution_mode or "").strip().lower()
    allowed = {item.value if isinstance(item, ExecutionMode) else str(item) for item in skill.execution_modes}
    if normalized not in allowed:
        raise RuntimeError(
            f"Skill '{skill.id}' does not declare execution mode '{execution_mode}'. Allowed: {sorted(allowed)}"
        )


def _extract_injected_block(*, original: str, rendered: str) -> str:
    normalized_original = original.rstrip()
    normalized_rendered = rendered.rstrip()
    if normalized_rendered.startswith(normalized_original):
        suffix = normalized_rendered[len(normalized_original):].lstrip("\n")
        return suffix if suffix else normalized_rendered
    return normalized_rendered


if __name__ == "__main__":
    raise SystemExit(main())
