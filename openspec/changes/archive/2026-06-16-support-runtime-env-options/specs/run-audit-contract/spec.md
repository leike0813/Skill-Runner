## ADDED Requirements

### Requirement: Runtime env audit projection MUST be redacted

Run audit snapshots, status/detail responses, management responses, bundles, and input manifests MUST NOT include raw `runtime_options.env` values.

#### Scenario: input manifest receives env request
- **WHEN** a request includes `runtime_options.env={"FOO":"secret"}`
- **THEN** request input audit snapshots MAY include the env variable name
- **AND** they MUST represent the value as redacted
- **AND** they MUST NOT contain the raw string `"secret"`

#### Scenario: internal env option is excluded from audit
- **WHEN** attempt preparation injects internal `__runtime_env`
- **THEN** audit/status/API projections MUST NOT expose `__runtime_env`
