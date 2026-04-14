## ADDED Requirements

### Requirement: Run audit MAY include engine-compatible schema artifacts without changing canonical truth

Run-scoped audit assets under `.audit/contracts/` MAY include engine-compatible structured-output artifacts as derived transport files.

#### Scenario: canonical artifacts remain primary while compat artifacts coexist
- **WHEN** runtime materializes an engine-compatible schema or prompt summary artifact
- **THEN** it MUST keep canonical `target_output_schema.json` and `target_output_schema.md` intact
- **AND** the derived compatibility artifacts MUST use distinct filenames under `.audit/contracts/`
- **AND** these derived artifacts MUST be treated as transport/audit assets rather than as replacements for canonical truth

#### Scenario: spawn-command audit remains sufficient to debug injected transport artifact
- **WHEN** the first attempt injects an engine-specific schema CLI argument
- **THEN** existing first-attempt command audit fields in `.audit/request_input.json` MUST remain sufficient to observe which transport artifact or inline schema shape was actually launched
- **AND** runtime MUST NOT require a second structured-output-specific command audit channel for this slice
