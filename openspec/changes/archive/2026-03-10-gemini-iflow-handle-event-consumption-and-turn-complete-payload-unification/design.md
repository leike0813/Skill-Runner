# Design

## Decision 1: SSOT-first gate
Implementation order is fixed:
1. runtime contract + invariants + SSOT docs
2. parser/live/lifecycle implementation
3. tests and docs verification

## Decision 2: `agent.turn_complete.data` is direct payload
- `agent.turn_complete.data` carries structured turn statistics directly.
- No `details` wrapper is used for this event type.
- Payload shape is engine-specific-but-structured under a generic object contract.

## Decision 3: run handle source is live semantic event only
- `lifecycle.run_handle` remains the only semantic source for session handle persistence.
- Live publisher consumes and persists handle immediately.
- Waiting lifecycle no longer extracts handle from raw output text.

## Decision 4: Gemini semantic extraction
- Batch JSON parse remains primary.
- `session_id` emits `lifecycle.run_handle`.
- `stats` is attached to `agent.turn_complete.data`.
- Semantic hit rows continue to suppress overlapping raw rows (with `raw_ref` retained).

## Decision 5: iFlow semantic extraction
- Parse stdout/stderr in block-first mode.
- Assistant message is extracted as block text (not line-by-line).
- `<Execution Info>...</Execution Info>` JSON provides:
  - `session-id` -> `lifecycle.run_handle`
  - remaining fields -> `agent.turn_complete.data`
- Channel drift correction remains enabled and emits diagnostics.

## Decision 6: Codex/OpenCode turn-complete payload parity
- Codex `turn.completed.usage` -> `agent.turn_complete.data`.
- OpenCode `step_finish.part.cost/tokens` -> `agent.turn_complete.data.cost/tokens`.
- Event types and naming remain unchanged.

## Decision 7: waiting_user hard requirement
- Before entering `waiting_user`, a persisted session handle must exist.
- Missing handle fails with `SESSION_RESUME_FAILED`.
