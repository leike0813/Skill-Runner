# Tasks

## 1. SSOT and contracts
- [x] Add `agent.turn_start` and `agent.turn_complete` to runtime contract schema.
- [x] Add `lifecycle.run_handle` to runtime contract schema with required `data.handle_id`.
- [x] Update statechart/sequence/api docs to mark turn markers as RASP-only.
- [x] Add invariants for turn marker ordering/uniqueness and FCMP exclusion.

## 2. Parser and live path
- [x] Add process-start hook to live emitter and trigger for Gemini/iFlow.
- [x] Upgrade Codex parser to support start/end marker mapping via profile.
- [x] Upgrade OpenCode parser to emit turn markers and process events.
- [x] Add Gemini/iFlow parse result flags for turn markers (`turn_started`, `turn_completed`).
- [x] Emit `lifecycle.run_handle` from Codex (`thread.started`) and OpenCode (`step_start.sessionID`).
- [x] Allow one source row to fan out to multiple semantic events (OpenCode `step_start` produces both turn-start and run-handle).

## 3. Raw suppression
- [x] Ensure semantic emissions suppress overlapping raw spans in live publisher.
- [x] Ensure raw suppression does not suppress semantic event fan-out.

## 4. run_handle persistence
- [x] Persist run handle immediately during live execution via run-level consumer callback.
- [x] On handle change, overwrite and emit diagnostic warning `RUN_HANDLE_CHANGED`.
- [x] Keep `persist_waiting_interaction.extract_session_handle(...)` as compatibility fallback for Gemini/iFlow.

## 5. Verification
- [x] Run runtime contract/invariant/protocol tests in `DataProcessing`.
- [x] Add/update tests for run-handle emission, immediate consumption, overwrite warning, and fallback compatibility.
