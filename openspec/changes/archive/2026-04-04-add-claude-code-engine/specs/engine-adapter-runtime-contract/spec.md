## MODIFIED Requirements

### Requirement: Supported engines include Claude

The runtime adapter layer SHALL treat `claude` as a first-class supported engine with a dedicated adapter package under `server/engines/claude/**`.

#### Scenario: Claude adapter is registered

- **WHEN** the engine adapter registry is initialized
- **THEN** it MUST validate and register the `claude` adapter profile
- **AND** `engine=claude` MUST resolve to a concrete execution adapter

### Requirement: Claude print-mode execution uses stream-json

Claude non-interactive execution SHALL run in print mode with `stream-json` output.

#### Scenario: Build Claude start command

- **WHEN** the runtime builds a Claude start command
- **THEN** it MUST invoke `claude -p`
- **AND** it MUST include `--output-format stream-json`
- **AND** it MUST include `--verbose`
- **AND** it MUST provide session-local settings via `--settings`

### Requirement: Claude parser extracts only stable semantics

Claude stream parsing SHALL only extract the semantic subset needed by Skill Runner.

#### Scenario: Parse Claude stream-json output

- **WHEN** Claude emits `assistant` and `result` NDJSON events
- **THEN** the parser MUST extract assistant text blocks
- **AND** it MUST extract tool-use blocks as process events
- **AND** it MUST prefer `result.structured_output` as final structured payload when present
- **AND** it MUST use `session_id` as the session handle source
