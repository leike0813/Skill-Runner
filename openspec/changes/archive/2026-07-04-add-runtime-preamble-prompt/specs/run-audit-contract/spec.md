## ADDED Requirements

### Requirement: Runtime preamble MUST be redacted from persisted audit input
Run audit inputs SHALL not persist raw `preamble_prompt` text.

#### Scenario: Request snapshot written
- **WHEN** request payload is written to request store, staging request JSON, or run input snapshot
- **THEN** `runtime_options.preamble_prompt` and `effective_runtime_options.preamble_prompt` MUST be redacted descriptors
- **AND** raw preamble text MUST NOT appear in those artifacts
