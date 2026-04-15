## Context

The project now has two strong signals for the target output-contract direction:

- phase 0A created a dedicated machine-readable invariant contract and target delta specs
- phase 1 created a run-scoped JSON Schema builder/materialization path

The remaining drift is in the repository's main documentation and main-spec expression. Those surfaces still describe implementation-era behavior such as YAML ask-user wrappers and interactive soft completion as if they were the intended steady-state contract.

This slice must correct that drift while respecting one hard boundary:

- `openspec/specs/*` remains unchanged in this phase; the new change records the intended updates as delta specs only.

## Goals / Non-Goals

**Goals**
- Align the main `docs/` surfaces with the JSON-only target contract.
- Express main-spec updates through a dedicated change with delta specs.
- Make the legacy status of `<ASK_USER_YAML>` explicit everywhere it still needs to be referenced.
- Make it clear that prompt-facing schema markdown is derived from a run-scoped machine schema artifact.

**Non-Goals**
- Do not modify runtime code, tests, or `openspec/specs/*`.
- Do not change public API or persisted event schema.
- Do not perform `openspec sync-specs` or archive the change.

## Decisions

### Decision 1: Docs are updated directly, main specs stay indirect
Update `docs/` now, but keep main spec changes in delta-spec form only.

Why:
- The user explicitly chose direct doc synchronization but no direct main-spec edits.
- This preserves a clean later step for `sync-specs` / verify / archive.

### Decision 2: Legacy behavior may remain documented only as rollout context
If legacy ask-user wrappers or soft completion must still be mentioned, they are labeled as:

- `legacy`
- `deprecated`
- `current implementation only`

Why:
- The docs must stop presenting old behavior as the target contract.
- Some operational readers still need to understand why current runtime behavior may differ temporarily.

### Decision 3: PendingInteraction stays shape-stable in docs
Documentation should state that `PendingInteraction` keeps its current external shape, while its target source shifts toward legal pending JSON projection.

Why:
- This is the intended compatibility boundary.
- It avoids implying a wire-shape change that this slice does not implement.

## Documentation Synchronization Rules

1. Replace normative `<ASK_USER_YAML>` language with pending JSON branch language.
2. Replace normative soft-completion language with explicit final/pending union-contract language.
3. When describing current implementation drift, label it as legacy rollout background, not target behavior.
4. Describe output-schema guidance as:
   - machine truth: materialized JSON Schema artifact
   - prompt guidance: markdown projection derived from that artifact

## Validation Plan

- Confirm the OpenSpec change has complete artifacts.
- Grep the updated docs and change files for `<ASK_USER_YAML>` and soft-completion wording.
- Allow legacy references only when explicitly labeled as deprecated/current-implementation context.
