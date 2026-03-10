# Tasks

## 1. SSOT and contracts
- [x] Update runtime contract to allow structured object payload for `agent.turn_complete.data` (no nested `details` requirement).
- [x] Update statechart/sequence/api docs to declare turn-complete structured payload semantics.
- [x] Update invariants wording to keep FCMP turn-marker exclusion and clarify RASP turn payload extension.

## 2. Parser semantics
- [x] Gemini parser: emit `run_handle` from `session_id`, emit `turn_complete_data` from `stats`, and keep semantic raw suppression.
- [x] iFlow parser: add block-first parse, extract `run_handle` + `turn_complete_data` from `<Execution Info>`, preserve drift correction diagnostics.
- [x] Codex parser: map `turn.completed.usage` to `turn_complete_data`.
- [x] OpenCode parser: map `step_finish.part.cost/tokens` to `turn_complete_data`.

## 3. Live and audit protocol
- [x] Make live publisher consume `turn_complete_data` for `agent.turn_complete` events.
- [x] Make audit builder consume parser `turn_complete_data` for `agent.turn_complete`.
- [x] Ensure run-handle immediate consumer remains the only persistence path.

## 4. Lifecycle hard-cut
- [x] Remove `extract_session_handle(...)` fallback from `persist_waiting_interaction`.
- [x] Require pre-existing persisted handle before waiting-user persistence, else fail `SESSION_RESUME_FAILED`.

## 5. Verification
- [x] Update unit tests for parser outputs (Gemini/iFlow/Codex/OpenCode turn_complete and run_handle).
- [x] Update lifecycle tests for waiting-user handle requirement and fallback removal.
- [x] Run runtime protocol/schema/invariant regression tests in `DataProcessing`.
