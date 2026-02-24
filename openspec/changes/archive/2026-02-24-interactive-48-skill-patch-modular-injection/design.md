## Overview

This change defines a deterministic patch pipeline for `SKILL.md` injection with module-level composition and idempotent markers.

## Decision 1: Modular patch plan

`SkillPatcher.build_patch_plan(...)` returns ordered modules:

1. Runtime enforcement (always)
2. Artifact redirection (only when artifacts exist)
3. Output format contract (always)
4. Output schema specification (only when output schema is available/valid)
5. Mode patch (`auto` or `interactive`)

Each module has:

- source template (or generated content),
- marker,
- rendered content.

## Decision 2: Template SSOT

The following files under `server/assets/templates` are the only static source of injected instructions:

- `patch_runtime_enforcement.md`
- `patch_output_format_contract.md`
- `patch_artifact_redirection.md`
- `patch_mode_auto.md`
- `patch_mode_interactive.md`

`patch_artifact_redirection.md` uses `{artifact_lines}` placeholder populated at runtime.

## Decision 3: Dynamic output schema patch

Add `skill_patch_output_schema.py` to generate:

- `### Output Schema Specification` block,
- field table with `__SKILL_DONE__` first row,
- JSON skeleton example.

Generation is tolerant:

- invalid or missing schema => skip this module + log warning.

## Decision 4: Server + harness unified path

- Adapters pass output schema context to `patch_skill_md`.
- `agent_harness.skill_injection` uses `patch_skill_md` directly (default `auto` mode), no separate completion-only branch.

## Decision 5: Legacy completion contract removal

- Remove `server/assets/configs/completion_contract.md` dependency from patch logic.
- Marker-specific completion contract append path is retired.

## Failure semantics

- Missing static template files => fail fast (`RuntimeError`).
- Schema generation failures => non-fatal; patch pipeline continues without schema block.
