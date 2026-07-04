## ADDED Requirements

### Requirement: Runtime options MUST support a constrained preamble prompt
The service SHALL accept `runtime_options.preamble_prompt` as a public run-scoped option.

#### Scenario: Raw preamble accepted
- **WHEN** a client creates a run with a non-empty string `runtime_options.preamble_prompt`
- **THEN** the value MUST be trimmed, newline-normalized, length-limited, and accepted
- **AND** persisted runtime options MUST contain only a redacted descriptor

#### Scenario: Invalid preamble rejected
- **WHEN** `runtime_options.preamble_prompt` is empty, non-string, too long, or contains disallowed control characters
- **THEN** the request MUST fail validation before the run is queued

#### Scenario: Descriptor accepted internally
- **WHEN** persisted runtime options contain a preamble descriptor with `redacted`, `sha256`, and `length`
- **THEN** runtime option validation MUST accept it for replay and recovery flows
