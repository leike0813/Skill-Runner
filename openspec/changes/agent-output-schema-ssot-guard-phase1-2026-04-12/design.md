## Context

The current runtime and main specs still describe a mixed output regime:

- `auto` may succeed without explicit `__SKILL_DONE__`
- `interactive` may soft-complete without explicit final intent
- `<ASK_USER_YAML>` is treated as a primary ask-user signal
- repair is described as a narrow post-extraction helper rather than a unified schema-convergence loop

That behavior matches the current implementation, so this slice must not rewrite runtime code or existing implementation-facing tests. Instead, it must capture the target JSON-only direction in a new OpenSpec change plus an independent machine contract that future implementation slices can follow safely.

Constraints:

- Do not modify `openspec/specs/*` directly in this slice.
- Do not change public API, FCMP event types, RASP event types, or `PendingInteraction` payload shape.
- Do not force existing runtime consistency tests to adopt new semantics before implementation exists.
- Keep the new machine contract independent from `session_fcmp_invariants.yaml`, which guards the current runtime state machine.

## Goals / Non-Goals

**Goals:**
- Define the target JSON-only output contract for `auto` and `interactive`.
- Fix `interactive` on a single union schema with explicit final and pending branches.
- Define repair retries as same-attempt internal rounds with bounded retries and explicit fallback semantics.
- Record audit expectations for schema extraction, validation, repair, and fallback.
- Add isolated machine-readable invariants and guard tests that can pass without runtime implementation changes.
- Reposition `ask_user.schema.yaml` as a capability vocabulary for `ui_hints`.

**Non-Goals:**
- Implement schema materialization, repair loop execution, or engine CLI schema flags.
- Update current runtime code paths, prompt templates, or main specs.
- Remove `<ASK_USER_YAML>` support from implementation in this slice.
- Change HTTP/API payloads, FCMP wire shapes, or persisted runtime event schema.

## Decisions

### Decision 1: Use an independent output-protocol invariant contract
Add `server/contracts/invariants/agent_output_protocol_invariants.yaml` instead of extending `session_fcmp_invariants.yaml`.

Why:
- `session_fcmp_invariants.yaml` is tied to the current runtime state machine and enforced against implementation today.
- The new output semantics are future-target SSOT and would immediately conflict with implementation-backed guards if merged into the existing session contract.

Alternative considered:
- Extending `session_fcmp_invariants.yaml` directly. Rejected because this slice is intentionally spec-first and must not force runtime behavior changes yet.

### Decision 2: Keep runtime event schema unchanged unless a hard gap appears
Do not modify `server/contracts/schemas/runtime_contract.schema.json` in this slice.

Why:
- The plan explicitly avoids public wire-shape drift before implementation.
- Existing orchestrator diagnostic and warning payloads are already flexible enough for the planned future repair/audit semantics.

Alternative considered:
- Pre-adding repair-specific audit payload shapes. Rejected because it would advertise public or persisted schema guarantees before any producer exists.

### Decision 3: Model `interactive` as a single union contract
Represent `interactive` output as one union contract with two explicit branches:
- final: `__SKILL_DONE__ = true` plus business output
- pending: `__SKILL_DONE__ = false` plus `message` and `ui_hints`

Why:
- The engine cannot know in advance whether a turn is final or pending, so dual entry contracts would create ambiguous orchestration.
- A single union contract gives one validation target per turn.

Alternative considered:
- Separate final/pending validation paths. Rejected because it leaks decision-making back into orchestration and patching.

### Decision 4: Treat repair as same-attempt internal convergence
Define repair retries as internal rounds within one attempt, with a default max of 3 retries and fallback-after-exhaustion to existing lifecycle decision logic.

Why:
- This matches the intended future semantics from the upgrade plan without prematurely changing `attempt_number`.
- It keeps repair as normalization, not conversation-state mutation.

Alternative considered:
- Representing each repair retry as a new attempt. Rejected because it would pollute attempt ownership, audit semantics, and max-attempt behavior.

### Decision 5: Reposition ask-user schema to `ui_hints` vocabulary only
Update `server/contracts/schemas/ask_user.schema.yaml` so it no longer defines a YAML wrapper protocol and instead documents the stable capability surface that future pending JSON payloads may reference through `ui_hints`.

Why:
- This preserves valuable hint vocabulary while removing the false impression that `<ASK_USER_YAML>` remains the primary protocol.

Alternative considered:
- Leaving the file untouched until implementation. Rejected because this slice explicitly fixes the contract role of the file.

## Risks / Trade-offs

- **[Spec drift between target SSOT and current implementation]** → Mitigation: keep all new semantics in a new OpenSpec change and a separate machine contract; do not alter implementation-backed invariant suites.
- **[ask_user schema consumers may still assume YAML wrapper semantics]** → Mitigation: limit this slice to a vocabulary-oriented file rewrite plus a light guard test; leave runtime consumers unchanged.
- **[Future implementers may overlook that the OpenSpec change name differs from the originally suggested dated form]** → Mitigation: state in artifacts that the CLI-safe name is `agent-output-schema-ssot-guard-phase1-2026-04-12` because OpenSpec forbids numeric-leading names.
- **[Audit schema may later need additive changes]** → Mitigation: explicitly document runtime event schema as unchanged in this slice and defer any additive contract to the implementation change if a real gap appears.

## Migration Plan

1. Create the OpenSpec change and record the target behavior in proposal, design, tasks, and delta specs.
2. Add the independent machine-readable output invariant contract.
3. Add isolated guard helpers and tests for the new contract.
4. Reposition `ask_user.schema.yaml` to a vocabulary-only role and add a light guard test.
5. Run targeted tests for the new guard surface plus existing invariant suites to confirm no implementation-facing regressions.

Rollback:

- Remove the new OpenSpec change directory, the independent output invariant contract, and the new guard tests.
- Restore the previous `ask_user.schema.yaml` if the vocabulary-only repositioning causes unintended test or documentation coupling.

## Open Questions

- None for this slice. Implementation-stage questions such as schema materialization paths, engine flag injection, and repair audit payload shape are intentionally deferred to later changes.
