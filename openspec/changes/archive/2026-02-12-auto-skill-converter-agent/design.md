## Context

Skill Runner currently requires a strict AutoSkill profile (`SKILL.md` + `assets/runner.json` + input/parameter/output schemas). Existing third-party skills often only provide a generic `SKILL.md` and are not directly executable by Skill Runner APIs.

This change introduces an Agent skill that performs deterministic conversion from a generic skill package to a Skill Runner-compatible package. The converter is intended to run as a normal interactive agent skill (outside or inside Skill Runner), and must produce predictable output, surface clear validation errors, and avoid making unsafe semantic guesses about unknown skill behaviors.

Constraints:
- Conversion flow should support interactive Q&A with the user as the primary mode, with optional non-interactive batch mode.
- Output package must satisfy Skill Runner install validation requirements.
- Identity and file layout must remain consistent (`skill_id`, directory name, and manifest identity).

Stakeholders:
- Skill authors who want quick migration.
- Platform maintainers who need standardized skills.
- Integrators who depend on stable installation and execution contracts.

## Goals / Non-Goals

**Goals:**
- Define a deterministic conversion pipeline for a generic skill package.
- Patch `SKILL.md` with automation-safe instructions and default execution conventions.
- Generate required `assets/runner.json` and schema files with conservative defaults.
- Generate a complete output skill package, including a bundled schema/runner reference document.
- Produce a conversion report (`warnings/errors/actions`) that explains all changes.
- Ensure generated package can pass `/v1/skill-packages/install` validation without manual edits for common cases.

**Non-Goals:**
- Fully infer business semantics from arbitrary prose-only skills.
- Auto-generate perfect domain-specific schemas for all unknown input/output contracts.
- Execute the converted skill during conversion as part of validation.
- Replace runtime/output correctness testing after conversion.

## Decisions

### Decision 1: Use a two-phase conversion pipeline (analyze -> materialize)

Pipeline:
1. Analyze source package (structure, metadata, existing assets, instruction patterns).
2. Materialize target package (patch/create files + validation report).

Alternatives considered:
- Single-pass direct rewrite: simpler but harder to explain and audit.
- Fully non-interactive conversion: faster for batch processing, but weak for ambiguous source skills.

Rationale:
- Two-phase flow gives traceability and deterministic behavior with clear failure points.

### Decision 2: Apply bounded, template-driven `SKILL.md` patching

Approach:
- Preserve original intent sections where possible.
- Add or rewrite a dedicated "Skill Runner execution contract" block:
  - runtime assumptions for Skill Runner execution
  - deterministic output location
  - required artifact writing conventions
  - failure handling expectations
- Add an explicit guidance line in `SKILL.md` that references `references/file_protocol.md` for schema/runner generation doubts.
- Do not rewrite domain content unless it conflicts with execution safety.

Alternatives considered:
- Full replacement of `SKILL.md`: too destructive, high risk of losing author intent.
- Minimal append-only patch: too weak when original instructions contradict automation.

Rationale:
- Bounded patching balances compatibility and enforceability.

### Decision 3: Generate conservative default schemas with explicit warnings

Approach:
- If source does not provide machine-readable contracts, generate minimal valid schemas:
  - `input.schema.json` with empty/default object plus optional placeholders
  - `parameter.schema.json` as object with no required fields by default
  - `output.schema.json` with explicit artifact contract placeholders
- Emit warnings for any inferred or placeholder fields.

Alternatives considered:
- Hard fail when schema inference is incomplete: robust but poor usability.
- Aggressive inference from prose: improves convenience but risks incorrect contracts.

Rationale:
- Conservative defaults keep conversion usable while making uncertainty explicit.

### Decision 4: Generate `runner.json` from policy templates + extracted metadata

Approach:
- Source of truth for `runner.json` fields:
  - identity from resolved `skill_id`
  - engines from configured defaults (and optionally inferred hints)
  - schema paths fixed to `assets/*.schema.json`
  - artifacts contract generated from output schema and conventions
- Enforce monotonic internal format version for converter output.

Alternatives considered:
- Copy runner from nearest sample skill: fragile and hard to reason about.
- Fully freeform generation: inconsistent across runs.

Rationale:
- Template + policy keeps output stable and testable.

### Decision 5: Validation parity with Skill Runner install checks

Approach:
- Converter runs the same structural/identity checks as skill-package install validator rules.
- Conversion fails fast on non-recoverable issues (e.g., invalid zip layout, identity mismatch).

Alternatives considered:
- Lightweight validation only: faster but defers errors to install step.

Rationale:
- Early parity validation reduces iteration cost and surprises.

### Decision 6: Produce explicit conversion manifest

Approach:
- Write `conversion_report.json` containing:
  - input summary
  - files created/modified
  - inferred defaults
  - warnings
  - blocking errors

Alternatives considered:
- Human-readable log only: not machine-consumable.

Rationale:
- Structured report supports automation pipelines and debugging.

### Decision 7: Bundle protocol reference document in output package

Approach:
- Copy project-level `docs/file_protocol.md` into converted package `references/file_protocol.md` as a built-in reference for generated `assets/*.schema.json` and `assets/runner.json`.
- If copy fails, conversion fails with actionable error (reference document is part of required complete package output).

Alternatives considered:
- Omit reference doc: smaller output but less maintainable and harder for users to adjust generated contracts.
- Link externally only: fragile in offline/distributed usage.

Rationale:
- Shipping a local reference document improves maintainability and reduces ambiguity for follow-up manual edits.

## Risks / Trade-offs

- [Over-conservative defaults reduce immediate usability] -> Mitigation: include actionable warnings and suggested manual follow-up edits.
- [Bounded patch may miss deeply implicit behavior] -> Mitigation: require conversion report acknowledgements for uncertain areas.
- [Policy templates may drift from runtime requirements] -> Mitigation: add contract tests that compare converter output against latest install validator expectations.
- [Different source skill styles produce uneven conversion quality] -> Mitigation: maintain a fixtures corpus with representative skill variants.

## Migration Plan

1. Add converter skill assets (templates, policies, and conversion scripts).
2. Add fixtures and tests for successful conversion and expected failures.
3. Document conversion usage and integration path with `/v1/skill-packages/install`.
4. Rollout in opt-in mode first (manual usage), then promote as recommended migration path.

Rollback:
- Remove/disable converter skill package without affecting existing runtime APIs.
- Keep generated outputs external; no persistent service state migration required.

## Open Questions

- Should engine defaults in generated `runner.json` be fixed to one engine or generated as a policy-driven allowlist?
- Should converter optionally run a dry validation execution against a smoke-test input set?
- Do we need strict mode (`fail_on_warning=true`) for CI pipelines?
