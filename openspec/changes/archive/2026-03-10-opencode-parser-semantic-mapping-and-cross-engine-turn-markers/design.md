# Design

## Decision 1: SSOT-first gate
Implementation is valid only after:
1. contract enum update (`agent.turn_start`, `agent.turn_complete`)
2. statechart/sequence docs alignment
3. invariants update (`RASP turn marker ordering + uniqueness`, `FCMP no assistant.turn_*`)

## Decision 2: RASP-only turn markers
- RASP carries turn markers.
- FCMP keeps existing types; no turn marker mapping.
- This preserves client-facing compatibility while improving audit traceability.

## Decision 3: Cross-engine turn-start semantics
- Codex: NDJSON `turn.started`
- OpenCode: NDJSON `step_start`
- Gemini/iFlow: process-start hook emits turn-start immediately (no first-output dependency)

## Decision 4: Turn-complete semantics
- Codex: NDJSON `turn.completed`
- OpenCode: NDJSON `step_finish`
- Gemini: parsed structured payload contains `response`
- iFlow: `<Execution Info>...</Execution Info>` block detected

## Decision 5: Raw suppression consistency
Any semantic emission with `raw_ref` adds suppression range, and overlapping raw spans are dropped.
This is engine-agnostic and enforced in live publisher.

## Decision 6: run_handle immediate consumption
- `lifecycle.run_handle` is emitted in RASP as soon as parser extracts a valid handle.
- Live emitter invokes a run-level consumer callback immediately after publishing the event.
- Consumer persists handle to run store without waiting for `persist_waiting_interaction`.

## Decision 7: Handle overwrite policy with diagnostics
- If persisted handle is missing: store directly.
- If new handle equals existing: no-op.
- If new handle differs: overwrite and emit diagnostic warning `RUN_HANDLE_CHANGED` with old/new summary.
- Diagnostic is observability-only and MUST NOT alter state transition semantics.

## Decision 8: Compatibility fallback remains
- `persist_waiting_interaction.extract_session_handle(...)` remains as fallback for engines that do not emit `lifecycle.run_handle` yet (current Gemini/iFlow path).
- Fallback removal is deferred to next batch after Gemini/iFlow eventized run-handle is introduced.

## Decision 9: Semantic fan-out from one source row is allowed
- One source row MAY produce multiple semantic events (e.g. OpenCode `step_start` -> `agent.turn_start` + `lifecycle.run_handle`).
- Raw suppression applies only to raw events and MUST NOT suppress semantic fan-out events.
