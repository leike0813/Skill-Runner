# Output Contract Prompt Injection SSOT

## Overview

This document defines the long-term source-of-truth model for runtime output contracts, engine translation, and the final `SKILL.md` prompt injection layout.

The core rule is simple:

- Canonical machine truth is the run-scoped JSON Schema artifact.
- Agent-facing text contract is injected only into runtime `SKILL.md`.
- Prompt contract text is derived dynamically from the same schema pipeline and is not persisted as a standalone run-scoped Markdown artifact.

## Source Of Truth

### Canonical schema

- Source input: the skill business schema `<skill_dir>/assets/output.schema.json`
- Canonical runtime artifact: `<run_dir>/.audit/contracts/target_output_schema.json`
- Owner: `server/services/orchestration/run_output_schema_service.py`

This canonical schema is the single machine-readable truth for the attempt-level output contract.

For `auto`, the canonical schema is the final wrapper schema.

For `interactive`, the canonical schema is the union schema:

- final branch: `__SKILL_DONE__ = true`
- pending branch: `__SKILL_DONE__ = false + message + ui_hints`

### Compat schema

- Compat schema is an engine transport artifact, not canonical truth.
- It exists only when the structured-output pipeline needs to translate the canonical schema into an engine-supported subset.
- Current example: Codex may materialize `.audit/contracts/target_output_schema.codex_compatible.json`.

Compat schema MUST stay downstream from the canonical schema. The canonical schema is never weakened to satisfy a specific engine.

### Prompt contract text

- Prompt contract text is a derived textual rendering of either the canonical schema or the engine-effective compat schema.
- It is built in memory and injected into runtime `SKILL.md`.
- It is also reused by repair prompts.
- It is not written to `.audit/contracts/*.md`.

## Unified Pipeline

The runtime pipeline is fixed:

1. Skill `output.schema.json`
2. `run_output_schema_service`
   - Builds canonical final wrapper or interactive union schema
   - Materializes canonical `.audit/contracts/target_output_schema.json`
3. `structured_output_pipeline`
   - Chooses canonical passthrough or engine compat translation from adapter profile
   - Produces the engine-effective machine schema
   - Produces the matching engine-effective prompt contract text
4. Dynamic contract builder
   - Renders field table, required/additionalProperties notes, artifact-field guidance, and examples
5. `skill_patcher`
   - Injects static templates plus the dynamic contract section into runtime `SKILL.md`
6. `run_output_convergence_service`
   - Reuses the same prompt contract text for repair prompts

This prevents drift between:

- CLI schema injection
- `SKILL.md` injected wording
- repair prompt wording

## Execution Mode Composition

Execution mode changes the injected prompt in two ways:

### Auto

- Uses the canonical final contract only
- `patch_mode_auto.md` adds execution policy
- It does not restate field-level schema details
- It explicitly forbids `__SKILL_DONE__ = false`

### Interactive

- Uses the canonical union contract or engine-effective compat contract
- Field-level pending details live only in the dynamic contract section
- `patch_mode_interactive.md` adds behavior policy only:
  - act autonomously when possible
  - ask at most one question per turn
  - choose exactly one branch per turn
- The interactive mode template must not duplicate `message`, `ui_hints`, `options`, or `files` field rules

## Final Runtime `SKILL.md` Composition

The injected runtime `SKILL.md` is assembled in this order:

1. Original skill-authored `SKILL.md`
2. `Runtime Enforcement`
   - Static source: `server/assets/templates/patch_runtime_enforcement.md`
3. `Runtime Output Overrides`
   - Static source: `server/assets/templates/patch_artifact_redirection.md`
   - Dynamic input: manifest artifact declarations
4. `Output Format Contract`
   - Static source: `server/assets/templates/patch_output_format_contract.md`
5. `Output Contract Details`
   - Static shell source: `server/assets/templates/patch_output_contract_details.md`
   - Optional static subtemplates: generic mode-specific note templates under `server/assets/templates/patch_output_contract_*.md`
   - Dynamic source: schema-driven placeholder rendering
6. `Execution Mode`
   - Static source: `patch_mode_auto.md` or `patch_mode_interactive.md`

Static sections define global policy. Dynamic sections define the current run's concrete schema contract.

## Engine Translation Rules

The adapter profile declares how structured output is handled for each engine:

- whether CLI schema injection is enabled
- whether the injected schema is canonical or compat-translated
- whether prompt contract text is canonical or compat-translated
- whether parsed payloads need canonicalization back into canonical shape

Current governance rules:

- Canonical schema remains the only machine truth.
- Engine-specific schema transport is a derived artifact.
- Prompt contract text MUST match the actual engine-effective machine schema.
- No engine may inject a compat schema while still showing canonical-only prompt details.

## Why Markdown Artifacts Were Removed

Run-scoped `.md` summary artifacts were removed because they created an unnecessary second prompt-facing persistence surface.

They caused three problems:

- duplicated truth between `.json` artifact and `.md` artifact
- drift risk between compat CLI schema and textual contract
- extra coupling between `SKILL.md` injection and audit file layout

The retained run-scoped artifact is the canonical `.json` machine contract because runtime validation, CLI injection, and audit debugging still need it.

The removed artifact is the standalone `.md` prompt summary because agent-facing text is fully represented by the final patched `SKILL.md` and repair prompt reuse.

## Implementation Anchors

- Canonical schema materialization:
  `server/services/orchestration/run_output_schema_service.py`
- Engine compat translation and prompt-contract selection:
  `server/runtime/adapter/common/structured_output_pipeline.py`
- Dynamic contract builder:
  `server/services/skill/skill_patch_output_schema.py`
  Generic prompt-contract text comes from static templates plus dynamic placeholder rendering.
  Engine-specific note text may remain in code when it is too specific for the shared template directory.
- Runtime `SKILL.md` assembly:
  `server/services/skill/skill_patcher.py`
- Repair prompt reuse:
  `server/services/orchestration/run_output_convergence_service.py`
