## ADDED Requirements

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
