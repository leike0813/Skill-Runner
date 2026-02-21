## MODIFIED Requirements

### Requirement: Temporary skill metadata must satisfy execution constraints
The system MUST require temporary skill metadata to provide a non-empty `artifacts` contract and a valid engine compatibility contract. Engine compatibility MUST be validated from optional `engines` and optional `unsupported_engines`: if `engines` is omitted or empty, candidate engines MUST default to all supported engines (`codex`, `gemini`, `iflow`) before applying `unsupported_engines`.

#### Scenario: Missing engines defaults to all supported engines for temporary skill
- **WHEN** temporary `runner.json` omits `engines` or provides an empty list
- **AND** `unsupported_engines` is omitted or excludes only a subset of supported engines
- **AND** `artifacts` is present and non-empty
- **THEN** the system accepts the temporary skill metadata and resolves effective supported engines from all supported engines minus `unsupported_engines`

#### Scenario: Reject unknown engine names in temporary metadata
- **WHEN** temporary `runner.json.engines` or `runner.json.unsupported_engines` contains an engine name outside `codex`, `gemini`, `iflow`
- **THEN** the system rejects the request as invalid

#### Scenario: Reject overlap between temporary allowlist and blocklist
- **WHEN** temporary `runner.json.engines` and `runner.json.unsupported_engines` share at least one engine name
- **THEN** the system rejects the request as invalid

#### Scenario: Reject effective empty temporary engine set
- **WHEN** the resolved effective supported-engine set for temporary skill becomes empty after applying `unsupported_engines`
- **THEN** the system rejects the request as invalid

#### Scenario: Reject invalid metadata contract
- **WHEN** temporary `runner.json` omits `artifacts` or declares an empty `artifacts` list
- **THEN** the system rejects the request as invalid
