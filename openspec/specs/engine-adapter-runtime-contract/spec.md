## MODIFIED Requirements

### Requirement: OpenCode-family adapters MUST share runtime stream semantics

Adapters for engines that emit OpenCode-family JSONL SHALL use a shared parser core for runtime stream semantics.

#### Scenario: Kilo uses OpenCode-family process event extraction
- **WHEN** Kilo emits `tool_use` rows in its JSONL stdout
- **THEN** the Kilo parser MUST extract process events using the same OpenCode-family mapping as OpenCode
- **AND** Kilo-specific `type=error` handling MUST remain adapter-specific

#### Scenario: OpenCode remains behaviorally compatible
- **WHEN** OpenCode emits existing JSONL runtime rows
- **THEN** its parser MUST continue to expose assistant messages, process events, turn markers, and run handles with the same public parse result fields

#### Scenario: OpenCode-family reasoning rows use shared extraction
- **WHEN** OpenCode or Kilo emits an explicit `type=reasoning` row
- **THEN** the adapter MUST extract it through the shared OpenCode-family parser core
- **AND** engine-specific parsers MUST NOT duplicate separate reasoning-row mapping logic

## ADDED Requirements

### Requirement: Runtime preamble MUST be injected only into the initial attempt prompt
Adapters SHALL inject client preamble text through the common prompt builder only for the first initial attempt.

#### Scenario: First attempt prompt
- **WHEN** attempt number is `1` and the run has a raw preamble secret
- **THEN** the rendered prompt MUST include a bounded client preamble section after the skill invoke line and before the skill body
- **AND** the section MUST state that it does not override service, engine, skill, safety, or output schema instructions

#### Scenario: Resume and repair prompts
- **WHEN** a prompt is rendered for an interaction reply, auth resume, recovery resume, retry attempt, or output repair
- **THEN** the runtime preamble MUST NOT be injected again
- **AND** internal `__prompt_override` MUST continue to replace the full effective prompt
