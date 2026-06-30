## ADDED Requirements

### Requirement: Kilo model catalog MUST preserve provider-aware identity
Kilo model catalog entries SHALL preserve discovered provider IDs and complete runtime model strings.

#### Scenario: Kilo Gateway model is validated
- **WHEN** model validation resolves a Kilo Gateway model such as `kilo/openai/gpt-5.2`
- **THEN** the returned model provider ID MUST be `kilo/openai`
- **AND** the returned model name MUST be `gpt-5.2`
- **AND** the runtime model MUST remain `kilo/openai/gpt-5.2`

#### Scenario: Kilo third-party model is validated
- **WHEN** model validation resolves a Kilo third-party model such as `openai-compatible/my-model`
- **THEN** the provider ID MUST match the model ID provider segment
- **AND** the runtime model MUST remain the complete model ID
