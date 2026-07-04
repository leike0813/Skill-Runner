## ADDED Requirements

### Requirement: Runtime preamble MUST participate in cache identity
Run cache identity SHALL include the normalized preamble prompt content hash.

#### Scenario: Cache key differs by preamble
- **WHEN** two otherwise identical auto runs use different `preamble_prompt` values
- **THEN** their cache keys MUST differ

#### Scenario: Non-cache runtime secrets remain excluded
- **WHEN** two otherwise identical auto runs differ only by `runtime_options.env`
- **THEN** their cache keys MUST remain equal
