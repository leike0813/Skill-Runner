# auth-detection-layer Specification

## Purpose
Define a single-source, parser-driven auth detection model for runtime execution.
## Requirements
### Requirement: Auth evidence declarations MUST be single-source
Auth evidence patterns MUST be declared in:
- engine-specific `adapter_profile.json` (`parser_auth_patterns.rules`)
- common fallback patterns (`server/engines/common/auth_detection/common_fallback_patterns.json`)

Runtime MUST NOT read legacy YAML rule packs.

#### Scenario: Legacy rule-pack source is retired
- **WHEN** runtime loads auth detection declarations
- **THEN** it MUST NOT read `server/engines/auth_detection/*.yaml`
- **AND** missing/invalid adapter/common declarations MUST fail validation paths.

### Requirement: Parser MUST perform one-pass auth signal classification
Each engine parser MUST match declared auth evidence and emit `auth_signal` directly.

`auth_signal` is the authoritative runtime auth classification result and includes:
- `required`
- `confidence` (`high|low`)
- `matched_pattern_id`
- optional `provider_id`
- optional `reason_code`

#### Scenario: Parser emits high-confidence signal for declared evidence
- **GIVEN** runtime output matches an engine-specific declared pattern
- **THEN** parser MUST emit `auth_signal.required=true` with `confidence=high`.

#### Scenario: Parser emits low-confidence signal for fallback evidence
- **GIVEN** runtime output misses engine-specific patterns but matches common fallback
- **THEN** parser MUST emit `auth_signal.required=true` with `confidence=low`.

### Requirement: Lifecycle MUST consume auth signal snapshot only
Execution lifecycle MUST consume only the execution-stage `auth_signal_snapshot` and MUST NOT run second-pass auth detection over parser diagnostics or combined text.

#### Scenario: No second-pass detect in lifecycle
- **WHEN** run lifecycle classifies terminal auth outcome
- **THEN** it MUST use `auth_signal_snapshot` from execution result
- **AND** it MUST NOT invoke rule-based detect over terminal output text again.

### Requirement: Waiting-auth transition MUST be high-confidence only
Only high-confidence auth signal MUST drive `waiting_auth` entry and terminal auth-required attribution.

Low-confidence auth signal is diagnostic-only and MUST NOT force `waiting_auth` or rewrite a terminal non-auth failure into `AUTH_REQUIRED`.

#### Scenario: High-confidence auth signal enters waiting_auth
- **GIVEN** `auth_signal.required=true` and `confidence=high`
- **AND** idle-blocking early-exit condition is satisfied (if process still blocked)
- **THEN** runtime MUST transition to `waiting_auth` flow.

#### Scenario: Low-confidence auth signal does not enter waiting_auth
- **GIVEN** `auth_signal.required=true` and `confidence=low`
- **THEN** runtime MUST keep it as diagnostic evidence only
- **AND** MUST NOT transition to `waiting_auth` based solely on that signal.

#### Scenario: Low-confidence auth signal does not rewrite terminal failure
- **GIVEN** `auth_signal.required=true` and `confidence=low`
- **AND** the process exits non-zero for a non-auth failure
- **WHEN** lifecycle normalizes the terminal result
- **THEN** terminal error code MUST NOT be `AUTH_REQUIRED`
- **AND** the low-confidence signal MUST remain available in audit diagnostics

### Requirement: RASP auth diagnostics MUST carry structured auth signal payload
RASP keeps existing diagnostic event envelope and MUST carry auth signal detail in `diagnostic.warning.data.auth_signal`.

#### Scenario: Structured auth diagnostic payload
- **WHEN** auth signal is persisted to RASP diagnostic stream
- **THEN** `diagnostic.warning.data` MUST include:
  - `code` (`AUTH_SIGNAL_MATCHED_HIGH|AUTH_SIGNAL_MATCHED_LOW`)
  - `auth_signal.matched_pattern_id`
  - `auth_signal.confidence`
  - optional `auth_signal.provider_id`
  - optional `auth_signal.reason_code`
- **AND** event category/type/source envelope semantics MUST remain unchanged.

### Requirement: Backend auth detection MUST use parser-signal single source
runtime auth detection MUST be parser-signal driven, with evidence declarations only from adapter profiles and common fallback patterns.

#### Scenario: runtime does not read legacy yaml rule packs
- **WHEN** backend loads auth detection declarations
- **THEN** it MUST NOT read `server/engines/auth_detection/*.yaml`
- **AND** parser MUST classify auth signal directly from declared match patterns.

#### Scenario: fallback signal is low-confidence only
- **GIVEN** engine-specific evidence is not matched
- **AND** common fallback evidence is matched
- **THEN** parser MUST emit `auth_signal.required=true` and `confidence=low`.
