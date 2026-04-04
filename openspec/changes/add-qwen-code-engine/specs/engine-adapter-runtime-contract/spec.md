## ADDED Requirements

### Requirement: Qwen is a first-class supported engine

The runtime adapter layer SHALL treat `qwen` as a first-class supported engine with a dedicated adapter package under `server/engines/qwen/**`.

#### Scenario: Qwen adapter is registered

- **WHEN** the engine adapter registry is initialized
- **THEN** it MUST validate and register the `qwen` adapter profile
- **AND** `engine=qwen` MUST resolve to a concrete execution adapter

### Requirement: Qwen non-interactive execution uses the top-level qwen CLI contract

Qwen non-interactive execution SHALL use the top-level `qwen` command with `stream-json` output and `--resume`-based session continuation.

#### Scenario: Build Qwen start command

- **WHEN** the runtime builds a Qwen start command
- **THEN** it MUST invoke the top-level `qwen` executable
- **AND** it MUST include `--output-format stream-json`
- **AND** it MUST include `--approval-mode yolo`
- **AND** it MUST include `-p "<prompt>"`

#### Scenario: Build Qwen resume command

- **WHEN** the runtime builds a Qwen resume command
- **THEN** it MUST invoke the top-level `qwen` executable
- **AND** it MUST include `--output-format stream-json`
- **AND** it MUST include `--approval-mode yolo`
- **AND** it MUST include `--resume <session_id>`
- **AND** it MUST include `-p "<prompt>"`

### Requirement: Qwen parser extracts stable non-live semantics

Qwen phase-1 stream parsing SHALL only extract the semantic subset needed by Skill Runner from non-live NDJSON output.

#### Scenario: Parse Qwen stream-json output

- **WHEN** Qwen emits NDJSON events
- **THEN** the parser MUST extract `session_initialized` for session handle recovery
- **AND** it MUST extract `assistant` payloads for assistant text
- **AND** it MUST extract `result` payloads for final result text
- **AND** live streaming support is not required in this phase

## MODIFIED Requirements

### Requirement: Engine enumeration includes qwen

The `ENGINE_KEYS` configuration SHALL include `qwen` in the tuple of supported engines.

#### Scenario: Engine keys registry

- **WHEN** the system loads engine keys
- **THEN** `qwen` MUST be present in the `ENGINE_KEYS` tuple
