# runtime-env-options Specification

## Purpose
定义 runtime environment options 的 run-local 隔离、secret vault 存储与验证约束。
## Requirements
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

### Requirement: Runtime options MUST support a constrained preamble prompt

The service SHALL accept `runtime_options.preamble_prompt` as a public run-scoped option.

#### Scenario: Raw preamble accepted
- WHEN a client creates a run with a non-empty string `runtime_options.preamble_prompt`
- THEN the value MUST be trimmed, newline-normalized, length-limited, and accepted
- AND persisted runtime options MUST contain only a redacted descriptor

#### Scenario: Invalid preamble rejected
- WHEN `runtime_options.preamble_prompt` is empty, non-string, too long, or contains disallowed control characters
- THEN the request MUST fail validation before the run is queued

#### Scenario: Descriptor accepted internally
- WHEN persisted runtime options contain a preamble descriptor with `redacted`, `sha256`, and `length`
- THEN runtime option validation MUST accept it for replay and recovery flows
### Requirement: CodeBuddy routing environment MUST be service managed

CodeBuddy requests MUST reject run-local overrides of CODEBUDDY_AUTH_TOKEN, CODEBUDDY_API_KEY, CODEBUDDY_INTERNET_ENVIRONMENT, CODEBUDDY_BASE_URL, and CODEBUDDY_CONFIG_DIR before cache lookup and process launch. The adapter MUST remove inherited values and inject managed values.

#### Scenario: Request attempts to change the environment
- **WHEN** runtime_options.env contains CODEBUDDY_INTERNET_ENVIRONMENT
- **THEN** validation fails without consulting cache or starting a subprocess
### Requirement: CodeBuddy cache policy MUST remain caller controlled

The integration MUST NOT force no_cache and MUST NOT add account identity or credential generation to the cache key; existing provider and model engine options remain cache identity inputs.

#### Scenario: Provider account is replaced
- **WHEN** a caller submits the same cacheable request without no_cache=true
- **THEN** normal cache policy applies and documentation warns that a previous cached result may be reused

