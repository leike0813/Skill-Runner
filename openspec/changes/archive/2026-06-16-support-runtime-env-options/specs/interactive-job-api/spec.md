## ADDED Requirements

### Requirement: Job requests MAY include run-local environment variables

The job API SHALL accept `runtime_options.env` as an object whose keys are environment variable names and whose values are strings for the current run only.

#### Scenario: create request with env
- **WHEN** a client creates a job with `runtime_options.env={"FOO":"bar"}`
- **THEN** the request is accepted if the env object passes validation
- **AND** subsequent API/status/detail surfaces MUST NOT expose the raw value `"bar"`

#### Scenario: env validation rejects unsafe shapes
- **WHEN** `runtime_options.env` is not an object, has more than 64 entries, contains a non-string value, contains a value longer than 8192 characters, or contains a key not matching `^[A-Z_][A-Z0-9_]{0,127}$`
- **THEN** the API rejects the request with a client error

#### Scenario: env validation rejects protected variables
- **WHEN** a client provides a protected variable such as `PATH`, `HOME`, `PYTHONPATH`, or `LD_LIBRARY_PATH`
- **THEN** the API rejects the request with a client error

#### Scenario: env does not affect cache key
- **WHEN** two otherwise identical cacheable requests differ only by `runtime_options.env`
- **THEN** they compute the same cache key
- **AND** callers that require env-sensitive output isolation MUST use `runtime_options.no_cache=true`
