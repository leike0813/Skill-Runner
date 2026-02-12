## Context

`skill-converter-agent` is currently usable inside Skill-Runner flows, but its I/O contract is biased to run-time artifacts (`zip` input + `run_dir` outputs). That makes normal interactive agent usage less ergonomic for users who already have a local skill directory and want to iteratively decide conversion details.

This change upgrades the converter to a dual-mode architecture:
- Interactive-first local directory mode (primary for human-in-the-loop usage)
- Existing zip mode (for Skill-Runner compatibility)

Both modes must share one conversion core so conversion semantics, validation outcomes, and generated package structure stay consistent.

Constraints:
- Output remains a complete install-ready package.
- `references/file_protocol.md` is mandatory in output.
- Patched `SKILL.md` must explicitly point to `references/file_protocol.md`.
- No behavior divergence between directory mode and zip mode, beyond input loading and question flow.

## Goals / Non-Goals

**Goals:**
- Support source input as local directory path in addition to zip package.
- Keep zip mode fully compatible with current Skill-Runner execution path.
- Introduce a shared conversion core module used by both entry modes.
- Preserve/strengthen current identity, schema, and contract validation behavior.
- Add parity tests proving equivalent conversion output for equivalent source content.

**Non-Goals:**
- Changing Skill-Runner install API behavior.
- Automatically inferring all domain semantics from prose-only skills.
- Replacing user decisions in ambiguous interactive scenarios.
- Introducing a new storage backend or persistent converter state.

## Decisions

### Decision 1: Split into adapter layer + shared conversion core

Approach:
- Keep lightweight wrappers for each input mode:
  - `zip` loader wrapper
  - `directory` loader wrapper
- Move transformation/validation/write logic into one shared core module.

Alternatives considered:
- Keep one monolithic script with branching: quick but harder to test and extend.
- Duplicate logic per mode: simpler wrappers, but guaranteed drift risk.

Rationale:
- Shared core provides deterministic behavior and lowers maintenance risk.

### Decision 2: Treat mode difference as input-loading and decision-policy only

Approach:
- Mode only changes:
  - source loading (`directory` vs `zip`)
  - ambiguity behavior (interactive prompt vs strict failure/default policy)
- Materialization output and validation rules remain identical.

Alternatives considered:
- Allow mode-specific output structure: more flexible but breaks parity guarantees.

Rationale:
- Users and tests can reason about one output contract.

### Decision 3: Keep complete output package as first-class artifact

Approach:
- Always produce:
  - converted skill directory
  - install-ready zip package
  - conversion report JSON
- Always include `references/file_protocol.md` in package.
- Always patch `SKILL.md` to reference `references/file_protocol.md`.

Alternatives considered:
- Directory-only output in interactive mode: convenient but inconsistent with install handoff.

Rationale:
- One artifact contract works for both interactive usage and API installation.

### Decision 4: Introduce explicit parity checks in tests

Approach:
- Build fixtures where the same source skill is fed through `directory` and `zip` modes.
- Compare key generated files:
  - `assets/runner.json`
  - three schema files
  - patched `SKILL.md` reference block

Alternatives considered:
- Snapshot only one mode: misses cross-mode regressions.

Rationale:
- Parity is a primary requirement for this change.

## Risks / Trade-offs

- [Interactive branch complexity increases] -> Mitigation: isolate question/decision policy from core conversion engine.
- [Mode parity regressions over time] -> Mitigation: enforce parity tests in CI for representative fixtures.
- [Local directory mode may include noisy/unexpected files] -> Mitigation: normalize and filter package content by allow/deny rules before output.
- [Path-safety assumptions can differ between zip and directory mode] -> Mitigation: apply canonical path validation in both modes before conversion.

## Migration Plan

1. Refactor existing converter script into:
   - shared core conversion module
   - mode wrappers for zip and directory inputs
2. Update converter `SKILL.md` to document dual-mode usage and interactive behavior.
3. Add/adjust tests:
   - existing zip flow compatibility
   - new directory flow
   - parity assertions
4. Keep old CLI flags working where possible; add new flags for directory mode with clear defaults.
5. Update docs for both usage paths.

Rollback:
- If issues appear, route both modes through existing zip-only wrapper temporarily while preserving core output contract.

## Open Questions

- Should directory mode support in-place conversion output next to source directory, or always require explicit output path?
- For interactive mode, should unresolved ambiguity default to fail-fast or maintain a recommended default with warning?
- Do we want a future third wrapper for “remote git repo source” using the same core?

