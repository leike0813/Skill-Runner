## Context

The project now has a target SSOT for JSON-only output contracts, but stage 0A intentionally stopped short of runtime implementation. The next safe step is to give every run a stable output schema artifact pair that downstream code can reference without re-deriving it.

Current constraints:

- The business output schema remains the source input.
- `interactive` runtime still cannot reliably consume the future pending JSON branch (`message + ui_hints + __SKILL_DONE__ = false`) as the live prompt protocol.
- Existing interactive patching and lifecycle behavior must stay backward-compatible in this phase.

## Goals / Non-Goals

**Goals**
- Materialize a single run-scoped target output schema artifact pair under `.audit/contracts/`.
- Derive both machine schema and prompt summary from one builder path.
- Produce an `interactive` union machine schema artifact without changing current interactive prompt semantics.
- Route materialized schema paths into internal `run_options` and first-attempt audit data.
- Remove raw output-schema rendering responsibility from `skill_patcher`.

**Non-Goals**
- Do not add engine CLI schema flags yet.
- Do not change repair loop behavior or attempt semantics.
- Do not change `run_interaction_lifecycle_service` pending extraction rules.
- Do not remove `<ASK_USER_YAML>` prompt compatibility in interactive mode.

## Decisions

### Decision 1: Run-scoped schema artifacts live under `.audit/contracts/`
Use fixed run-relative paths:

- `.audit/contracts/target_output_schema.json`
- `.audit/contracts/target_output_schema.md`

Why:
- They are audit assets tied to the run rather than to any individual attempt.
- Start/resume can reuse the same path without drift.

### Decision 2: Machine schema and prompt markdown come from one service
Add `run_output_schema_service` as the only builder/materializer entry point.

Why:
- It removes duplicate schema rendering logic from patching and future adapter code.
- It keeps the materialized JSON Schema as the single source of truth while still allowing a prompt-safe markdown projection.

### Decision 3: Interactive machine schema can advance before interactive prompt protocol
Generate the full `interactive` union schema artifact now, but keep prompt-side interactive compatibility.

Why:
- The machine artifact is needed for audit and future CLI/schema enforcement work.
- The current runtime still depends on legacy ask-user heuristics for mid-turn waiting, so switching the prompt contract now would be premature.

### Decision 4: Stable schema artifact paths belong in `run_options` and request-input audit
Expose run-relative schema artifact paths through internal reserved `run_options` keys and first-attempt audit fields.

Why:
- Later CLI flag integration can reuse the same stable keys.
- The request input snapshot becomes the stable audit anchor for which schema contract the run used.

## Risks / Trade-offs

- **Interactive prompt docs and machine schema will intentionally diverge in this phase**:
  Mitigation: make the markdown explicitly state that the machine artifact includes the pending branch while the prompt section only documents the final completion object.
- **Legacy tests may still assume patcher reads raw schema files**:
  Mitigation: move tests to assert materialized markdown consumption instead of raw-schema loading.
- **Missing output schema must not hard-fail bootstrap in this layer**:
  Mitigation: return an empty materialization result and skip artifact writes, while preserving upstream schema validation behavior.

## Migration Plan

1. Add the implementation change artifacts.
2. Introduce the run output schema materialization service and stable artifact paths.
3. Wire bootstrapper and job lifecycle to consume the new service.
4. Refactor `skill_patcher` to accept precomputed markdown.
5. Update tests and validate the affected orchestration/patching suites.
