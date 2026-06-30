## ADDED Requirements

### Requirement: OpenCode-family adapters MUST share runtime stream semantics

Adapters for engines that emit OpenCode-family JSONL SHALL use a shared parser core for runtime stream semantics.

#### Scenario: Kilo uses OpenCode-family process event extraction
- **WHEN** Kilo emits `tool_use` rows in its JSONL stdout
- **THEN** the Kilo parser MUST extract process events using the same OpenCode-family mapping as OpenCode
- **AND** Kilo-specific `type=error` handling MUST remain adapter-specific

#### Scenario: OpenCode remains behaviorally compatible
- **WHEN** OpenCode emits existing JSONL runtime rows
- **THEN** its parser MUST continue to expose assistant messages, process events, turn markers, and run handles with the same public parse result fields
