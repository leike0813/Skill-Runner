## Context

The current `skill-converter-agent` implementation relies on multiple conversion scripts that perform deterministic rule-based transformation. This conflicts with the intended nature of an Agent skill, where semantic understanding and decision-making should primarily come from the LLM workflow defined in `SKILL.md`.

At the same time, conversion output must still satisfy strict Skill-Runner install contracts. Therefore, we need a prompt-first architecture with minimal scripting: conversion decisions and file generation are driven by `SKILL.md`, and scripts are only used for final contract validation.

Because the skill is executed in agent runtime context, final validation cannot depend on importing server internals at runtime. Validator logic must exist inside the skill package.

## Goals / Non-Goals

**Goals:**
- Make `SKILL.md` the primary conversion logic contract and execution flow.
- Remove conversion scripts that perform transformation logic.
- Keep only one final validation script in the skill package.
- Embed validator logic equivalent to project `SkillPackageValidator` inside the skill package.
- Preserve required output contract:
  - complete install-ready package
  - bundled `references/file_protocol.md`
  - patched/generated `SKILL.md` explicitly references `references/file_protocol.md`

**Non-Goals:**
- Building a new generic code generation engine outside agent execution flow.
- Coupling skill runtime validation to `server/services` imports.
- Expanding validator scope beyond install-contract parity.
- Redesigning `/v1/skill-packages/install` behavior.

## Decisions

### Decision 1: Prompt-first conversion architecture

Approach:
- Move conversion orchestration into `SKILL.md`:
  - content parse
  - task type classification
  - convertibility decision (`not_convertible` / `convertible_with_constraints` / `ready_for_auto`)
  - conversion strategy selection and generation
- Treat script execution as final gate only (validation step).

Alternatives considered:
- Keep hybrid conversion logic in scripts + prompts: easier migration but continued ambiguity in responsibility.
- Script-first conversion with prompt augmentation: predictable but fails the intended semantic-driven behavior.

Rationale:
- This aligns capability design with agent strengths and your stated product direction.

### Decision 2: Single validator script + embedded validator module

Approach:
- Keep one executable script:
  - `validate_converted_skill.py`
- Add one embedded module containing validator logic equivalent to `SkillPackageValidator`.
- Final validator returns machine-readable pass/fail + reason output.

Alternatives considered:
- No script at all: no reliable machine gate before packaging output handoff.
- Directly import `server/services/skill_package_validator.py`: brittle in non-project runtime contexts.

Rationale:
- Preserves independent execution while retaining strict install-contract checks.

### Decision 3: Validation parity as a maintained contract

Approach:
- Define parity tests to compare key validation behaviors between embedded validator and project validator.
- Maintain an explicit compatibility checklist for required rules:
  - top-level zip directory rule
  - path safety checks
  - required files and schema references
  - identity consistency
  - engines/artifacts/version checks

Alternatives considered:
- Best-effort parity by manual sync: high drift risk.

Rationale:
- Explicit parity checks prevent silent behavior divergence over time.

### Decision 4: Keep dual source usability at instruction level

Approach:
- In `SKILL.md`, keep both source paths:
  - directory-first interactive usage
  - zip-based usage for runner compatibility
- Do not enforce dual wrapper scripts; source handling is part of agent instructions.

Alternatives considered:
- Separate script wrappers per mode: contradicts minimal-script objective.

Rationale:
- Keeps usability while preserving prompt-first architecture.

## Risks / Trade-offs

- [LLM conversion variability] -> Mitigation: enforce deterministic output contract via final validator gate.
- [Embedded validator drift from project validator] -> Mitigation: add parity tests and explicit sync checkpoints.
- [Prompt complexity in `SKILL.md`] -> Mitigation: structure into staged sections with clear decision outcomes.
- [Reduced script automation for conversion internals] -> Mitigation: document strict generation steps and required artifacts in `SKILL.md`.

## Migration Plan

1. Rewrite `skills/skill-converter-agent/SKILL.md` to prompt-first staged conversion workflow.
2. Remove conversion logic scripts (`convert_skill.py`, `converter_core.py`).
3. Add embedded validator module and final validator script.
4. Update schemas and runner metadata to reflect validator-only scripting behavior.
5. Replace current converter tests with:
   - validator behavior tests
   - parity tests against project validator
   - contract tests for required output references.

Rollback:
- Restore previous converter scripts from git history and switch `SKILL.md` execution path back to script mode.

## Open Questions

- Should parity tests run on every CI pipeline or only on converter-related changes?
- Should validator output include normalized error codes in addition to messages?
- Do we need a documented version tag for embedded validator parity (e.g., `validator_contract_version`)?

