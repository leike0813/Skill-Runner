## Context

The current interactive path still treats LLM-emitted `ask_user` payload as a control-plane artifact.
That creates unnecessary coupling between business completion and model output formatting.

## Goals

1. Make interactive completion deterministic and model-format-independent.
2. Preserve optional `ask_user` enrichments without making them mandatory.
3. Keep auto-mode success criteria practical and backward compatible.
4. Prevent malformed `ask_user` from being misrouted into output validation failure paths.
5. Add bounded interactive retry guard via `runner.json.max_attempt`.

## Non-Goals

1. This change does not remove pending/reply endpoints.
2. This change does not remove `kind/options/ui_hints` fields from API payloads immediately (compatibility retained).
3. This change does not redesign frontend visual layout.

## Decisions

### Decision 1: Interactive completion gate is dual-track

For `execution_mode=interactive`, completion evidence is:
- strong evidence: `__SKILL_DONE__` detected;
- soft evidence: done marker missing, but output passes schema validation.

If neither evidence exists and process is not interrupted, the run transitions to `waiting_user` unless `max_attempt` is reached.

### Decision 2: Auto completion gate is output-validity-first

For `execution_mode=auto`, done marker is not required.
A run can complete successfully if final output passes schema validation and runtime execution succeeds.

### Decision 3: Done marker is control-only in all modes

`__SKILL_DONE__` is stripped before output schema validation in both `auto` and `interactive` modes.
It must never participate as a business field in validation.

### Decision 3.1: Done marker detection MUST be stream-format tolerant and unified

Done marker detection must accept both:
- plain JSON marker text (`"__SKILL_DONE__": true`);
- escaped marker text inside NDJSON string payloads (`\"__SKILL_DONE__\": true`).

Runtime lifecycle gating and audit completion classification MUST use the same detector semantics to avoid drift.

### Decision 4: ask_user is optional enrichment

`ask_user` may be parsed to enrich pending payload (`ui_hints/context/options`), but:
- it is not required for entering `waiting_user`;
- malformed payload does not cause immediate run failure;
- malformed payload does not get treated as final business output for schema validation.
- recommended transport for `ask_user` hints is non-JSON structured text (YAML block) in assistant stream, to reduce accidental overlap with business output JSON.

### Decision 4.1: soft completion MUST exclude ask_user-signaled turns

Ask_user hints (legacy JSON envelope or YAML envelope) are observability/pending enrichment only.
They MUST NOT be used as lifecycle gate predicates for completion/failure decisions.

### Decision 5: Backend-owned pending baseline

When interactive turn ends without done marker, backend always builds a normalized pending payload:
- `interaction_id`: backend-generated monotonic id (attempt-based)
- `prompt`: from final assistant message of the turn, else fallback prompt
- `kind`: compatibility value only (default `open_text`)
- optional enriched fields if safe to parse

### Decision 6: max_attempt is an interactive-only stop condition

`runner.json.max_attempt` is optional (`>=1`) and only applied to `interactive` mode.

Stop rule:
- when `attempt_number >= max_attempt` and current turn has neither strong nor soft completion evidence, run MUST fail with `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`.
- when `max_attempt` is absent, interactive attempts are unbounded.

### Decision 7: Stable diagnostics for soft completion and attempt exhaustion

The system records stable diagnostics in normalized result and audit metadata:
- warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER` when soft evidence is used to complete interactive run;
- error `INTERACTIVE_MAX_ATTEMPT_EXCEEDED` when max attempts are exhausted without completion evidence.

### Decision 8: Marker presence does not bypass terminal output validity

If a marker is detected but output parsing/schema validation fails in the same turn, lifecycle MUST end in `failed`.
The system MUST NOT fall back to `waiting_user` in this case.

## Architecture Notes

1. Orchestrator decides lifecycle first, then output validation:
   - `interactive + done found` => complete path
   - `interactive + done missing + output valid` => terminal success with warning
   - `interactive + done missing + output invalid` => waiting_user or max-attempt failure
   - `auto` => output validation as terminal decision
2. Protocol translator emits `user.input.required` from persisted pending state, not from ad-hoc parsing of assistant message JSON blocks.
3. UI should source pending prompt/id from pending/status/protocol events, not from parsing assistant text blobs.

## Risks and Mitigations

1. Risk: Some existing tests rely on strict ask_user envelope checks.
   - Mitigation: update tests to verify fallback pending generation and non-fatal malformed ask_user behavior.
2. Risk: Existing clients assume `kind` semantics.
   - Mitigation: keep `kind` field for compatibility while clarifying it is advisory only.
3. Risk: Silent waiting loops when model never emits done marker.
   - Mitigation: add `max_attempt` bound plus timeout/reply/cancel guards and observability diagnostics.
