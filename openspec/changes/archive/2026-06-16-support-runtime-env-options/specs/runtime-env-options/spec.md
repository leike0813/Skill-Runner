## ADDED Requirements

### Requirement: Runtime env options MUST be run-local and secret-aware

The system SHALL support `runtime_options.env` as a run-local environment overlay whose raw values are validated, stored only in a secret vault, loaded for execution, and excluded from normal persistence and cache key construction.

#### Scenario: raw env follows the secret path
- **WHEN** a request includes `runtime_options.env={"FOO":"secret"}`
- **THEN** raw value `"secret"` is written only to the request-scoped env vault
- **AND** normal request records, audit snapshots, status/detail responses, and bundles expose only a redacted projection

#### Scenario: env is local to one run
- **WHEN** a run executes with env injected from `runtime_options.env`
- **THEN** only that run's adapter subprocess environment receives the values
- **AND** global process environment and later runs without env remain unchanged

#### Scenario: env can be restored after restart
- **WHEN** a queued, retried, or resumed run declares env
- **THEN** attempt preparation reloads raw values from the request-scoped vault
- **AND** if the vault entry is missing, the run fails with `RUNTIME_ENV_SECRET_MISSING`
