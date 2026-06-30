## ADDED Requirements

### Requirement: Engine auth UI MUST hide removed providers
The management UI SHALL list only currently supported provider-aware auth options.

#### Scenario: Removed providers are absent
- **WHEN** engine auth providers are rendered
- **THEN** OpenCode and Kilo MUST NOT show `Google (AntiGravity)`
- **AND** Qwen MUST NOT show `Qwen OAuth (Free)`

### Requirement: Engine auth UI MUST show new API-key providers
The management UI SHALL show newly supported API-key providers through the existing provider-aware UI.

#### Scenario: New providers are visible
- **WHEN** engine auth providers are rendered
- **THEN** OpenCode and Kilo MUST show the new common API-key providers
- **AND** Qwen MUST show current Qwen preset API-key providers
