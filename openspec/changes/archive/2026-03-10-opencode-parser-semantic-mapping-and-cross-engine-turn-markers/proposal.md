# Change: opencode-parser-semantic-mapping-and-cross-engine-turn-markers

## Why
- `opencode` parser still lacks full process-semantic mapping parity with Codex/Gemini upgrades.
- Turn markers need unified cross-engine semantics without leaking engine-specific logic into core runtime.
- Existing runtime code already started consuming `agent.turn_*`, but SSOT/contract guardrails must be finalized first.

## What Changes
1. Add RASP-only turn markers to runtime contract:
   - `agent.turn_start`
   - `agent.turn_complete`
2. Add RASP-only run handle lifecycle event:
   - `lifecycle.run_handle` with `data.handle_id`
3. Keep FCMP stable:
   - no `assistant.turn_*`
4. Upgrade `opencode` parser:
   - `step_start` -> `agent.turn_start`
   - `step_finish` -> `agent.turn_complete`
   - first `step_start.sessionID` per attempt -> `lifecycle.run_handle`
   - `tool_use` mapped to generic process types:
     - `bash`/`grep` -> `command_execution`
     - others -> `tool_call`
5. Gemini/iFlow turn-start behavior:
   - emit turn-start immediately at attempt process start
6. Global raw suppression rule:
   - semantic-hit lines (`assistant_message` / `process_event` / `turn_marker`) suppress matching raw spans
7. Immediate run-handle consumption:
   - consume and persist run handle as soon as `lifecycle.run_handle` is published in run lifecycle
   - keep `persist_waiting_interaction.extract_session_handle(...)` fallback for Gemini/iFlow until next batch

## Scope
- Runtime contracts, invariants, parser implementations, live publisher behavior, and protocol docs.
- No HTTP route additions/removals.
- No FCMP state-machine semantic expansion.
