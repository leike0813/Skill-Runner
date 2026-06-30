## ADDED Requirements

### Requirement: Kilo MUST be a first-class profile-driven engine

The runtime adapter layer SHALL treat `kilo` as a supported engine with a dedicated adapter package under `server/engines/kilo/**`.

#### Scenario: Kilo adapter is registered

- **WHEN** the engine adapter registry is initialized
- **THEN** it MUST validate and register the Kilo adapter profile
- **AND** `engine=kilo` MUST resolve to a concrete execution adapter

### Requirement: Kilo execution MUST use run JSONL mode

Kilo non-interactive execution SHALL use `kilo run` with JSON output and automatic approval.

#### Scenario: Build Kilo start command

- **WHEN** the runtime builds a Kilo start command
- **THEN** it MUST invoke the profile-resolved Kilo executable
- **AND** it MUST include `run --format json --auto`
- **AND** it MUST include `--model <model>` when a model is selected
- **AND** it MUST append the rendered prompt as the message

#### Scenario: Build Kilo resume command

- **WHEN** the runtime builds a Kilo resume command
- **THEN** it MUST include `run --format json --auto --session <sessionID>`
- **AND** it MUST include `--model <model>` when a model is selected
- **AND** it MUST append the rendered prompt as the message

### Requirement: Kilo parser MUST extract stable JSONL semantics

Kilo stream parsing SHALL extract Skill Runner turn semantics from stdout JSONL rows.

#### Scenario: Parse successful Kilo JSONL output

- **WHEN** Kilo emits `step_start`, `text`, and `step_finish` JSONL rows
- **THEN** the parser MUST extract the top-level `sessionID`
- **AND** it MUST extract assistant text from `part.text`
- **AND** it MUST expose final token/cost diagnostics when present

#### Scenario: Parse Kilo error JSONL output

- **WHEN** Kilo emits a `type=error` JSONL row
- **THEN** the parser MUST produce failed turn semantics
- **AND** the failure MUST be honored even if the process exit code is `0`

### Requirement: Engine enumeration includes kilo

The active engine key registry SHALL include `kilo`.

#### Scenario: Engine keys registry

- **WHEN** the system loads active engine keys
- **THEN** `kilo` MUST be present in `ENGINE_KEYS`
