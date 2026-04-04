## ADDED Requirements

### Requirement: Qwen auth error detection MUST be implemented

The auth detection layer SHALL implement Qwen-specific error pattern matching for the currently supported failure signals.

#### Scenario: Detect Qwen OAuth token expired

- **WHEN** Qwen output contains `OAuth.*token.*expired` or `401.*Unauthorized`
- **THEN** the detector MUST identify it as `qwen_oauth_token_expired`

#### Scenario: Detect Qwen API key missing

- **WHEN** Qwen output contains `API key is missing` or `Invalid API key`
- **THEN** the detector MUST identify it as `qwen_api_key_missing`

### Requirement: Qwen auth patterns MUST be configurable

Qwen auth detection patterns SHALL be defined in `adapter_profile.json`.

#### Scenario: Load Qwen auth patterns from profile

- **WHEN** the Qwen adapter is initialized
- **THEN** it MUST load `parser_auth_patterns` from `adapter_profile.json`
- **AND** the patterns MUST be applied to runtime output analysis

## MODIFIED Requirements

### Requirement: Auth detector registry includes qwen

The auth detector registry SHALL include `qwen` as a supported engine.

#### Scenario: Qwen detector is registered

- **WHEN** the auth detector registry is initialized
- **THEN** it MUST register `QwenAuthDetector` for `engine=qwen`
- **AND** `detector_registry.resolve("qwen")` MUST return a valid detector instance
