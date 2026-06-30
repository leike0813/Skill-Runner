## Why

Kilo stdout JSONL is an OpenCode-family stream, but its adapter currently parses only text, turn markers, errors, and session handles. As a result, Kilo `tool_use` rows fall through as raw output instead of becoming auditable RASP/FCMP process events.

Timeout and canceled Kilo attempts also expose a protocol gap: when the engine stream has no `type=error`, audit materialization can lack an explicit semantic failure marker even though attempt status and completion metadata identify an interrupted terminal state.

## What Changes

- Introduce a shared OpenCode-family runtime stream parser core for OpenCode-shaped JSONL streams.
- Make OpenCode and Kilo use that common core for runtime stream parsing and live process-event emission.
- Preserve Kilo-specific `type=error` auth/failure extraction and legacy final-output parse behavior.
- Emit Kilo `tool_use` rows as `agent.command_execution` or `agent.tool_call`, and therefore as FCMP assistant process events.
- Add RASP fallback `agent.turn_failed` evidence when attempt status/completion indicates failed, canceled, or interrupted terminal execution and the parser did not emit a failure marker.

## Capabilities

### New Capabilities

- `runtime-parser-capability-contract`: Kilo is an OpenCode-family JSONL parser profile with process event extraction.

### Modified Capabilities

- `engine-adapter-runtime-contract`: OpenCode-family adapters share runtime stream semantics instead of duplicating parser behavior.
- `runtime-audit-contract`: interrupted terminal attempts must have semantic failure evidence even without engine error rows.
- `session-runtime-invariant-contract`: FCMP terminal state is governed by orchestrator status/completion while RASP can preserve both engine stream evidence and terminal failure evidence.

## Impact

- Updates parser common code, OpenCode and Kilo stream parsers, parser capability contract, protocol projection fallback, and focused unit tests.
- No public HTTP API, run request DTO, auth API, or model registry API changes.
- Historical audit artifacts are not rewritten automatically; they can be regenerated through existing materialization/rebuild flows.
