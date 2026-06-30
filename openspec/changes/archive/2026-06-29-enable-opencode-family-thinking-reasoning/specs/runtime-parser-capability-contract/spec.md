## MODIFIED Requirements

### Requirement: Kilo runtime parser MUST extract process events

The runtime parser capability contract SHALL declare Kilo process event extraction support.

#### Scenario: Kilo tool_use rows become process events
- **WHEN** Kilo emits a `tool_use` row for `bash` or `grep`
- **THEN** the parser MUST emit a `command_execution` process event

#### Scenario: Kilo non-command tool_use rows become tool calls
- **WHEN** Kilo emits a `tool_use` row for `apply_patch` or another non-command tool
- **THEN** the parser MUST emit a `tool_call` process event

#### Scenario: Kilo reasoning tokens remain usage metadata
- **WHEN** Kilo emits `step_finish.part.tokens.reasoning`
- **THEN** the parser MUST retain it in turn completion token data
- **AND** it MUST NOT emit `agent.reasoning` unless Kilo emits an explicit reasoning text row

#### Scenario: Kilo explicit reasoning rows become reasoning process events
- **WHEN** Kilo emits a `type=reasoning` row with reasoning text
- **THEN** the parser MUST emit a `reasoning` process event
- **AND** runtime projection MUST expose RASP `agent.reasoning` and FCMP `assistant.reasoning`

## ADDED Requirements

### Requirement: OpenCode-family parser MUST extract explicit reasoning rows

The shared OpenCode-family runtime parser SHALL extract explicit reasoning text rows as process events.

#### Scenario: OpenCode explicit reasoning row
- **WHEN** OpenCode emits a `type=reasoning` row with `part.text`
- **THEN** the parser MUST emit a `reasoning` process event with that text
- **AND** the text MUST NOT be added to assistant messages

#### Scenario: Reasoning token counts remain metadata
- **WHEN** an OpenCode-family engine emits `step_finish.part.tokens.reasoning`
- **THEN** the parser MUST retain the token count in turn completion data
- **AND** it MUST NOT infer a reasoning process event from tokens alone
