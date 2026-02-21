## MODIFIED Requirements

### Requirement: Enforce engine declaration
The system MUST validate `assets/runner.json` engine compatibility using `engines` (optional allowlist) and `unsupported_engines` (optional blocklist). If `engines` is omitted or empty, the system MUST treat the candidate set as all supported engines (`codex`, `gemini`, `iflow`) before applying `unsupported_engines`.

#### Scenario: Missing engines defaults to all supported engines
- **WHEN** `assets/runner.json` omits `engines` or provides an empty list
- **AND** `unsupported_engines` is omitted or excludes only a subset of supported engines
- **THEN** the system accepts the package and resolves effective supported engines from all supported engines minus `unsupported_engines`

#### Scenario: Unknown engine name is rejected
- **WHEN** `assets/runner.json.engines` or `assets/runner.json.unsupported_engines` contains an engine name outside `codex`, `gemini`, `iflow`
- **THEN** the system rejects the package as invalid

#### Scenario: Overlap between allowlist and blocklist is rejected
- **WHEN** `assets/runner.json.engines` and `assets/runner.json.unsupported_engines` share at least one engine name
- **THEN** the system rejects the package as invalid

#### Scenario: Effective empty engine set is rejected
- **WHEN** the resolved effective supported-engine set becomes empty after applying `unsupported_engines`
- **THEN** the system rejects the package as invalid
