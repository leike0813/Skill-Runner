## ADDED Requirements

### Requirement: Raw runtime env MUST be stored in a request-scoped secret vault

The run store layer SHALL keep raw `runtime_options.env` values out of normal request/run rows and persist them only in a local secret vault keyed by request id.

#### Scenario: vault file is created with restrictive permissions
- **WHEN** a request with runtime env is created
- **THEN** the system writes `data/run_secrets/<request_id>.env.json`
- **AND** the directory permissions are `0700` where supported
- **AND** the file permissions are `0600` where supported

#### Scenario: redacted runtime options are persisted
- **WHEN** the request record is stored
- **THEN** `runtime_options.env` and `effective_runtime_options.env` contain only redacted projections or env names
- **AND** raw env values are not present in the DB row

#### Scenario: missing declared env secret fails execution
- **WHEN** persisted runtime options declare env but the vault file is missing
- **THEN** attempt preparation fails the run with error code `RUNTIME_ENV_SECRET_MISSING`

#### Scenario: cleanup removes env secret
- **WHEN** request/run cleanup deletes request records
- **THEN** matching env secret files are deleted from the vault
