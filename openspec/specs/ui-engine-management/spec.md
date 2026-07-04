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

### Requirement: Kilo UI shell MUST use Kilo-local config hardening

Kilo UI shell sessions SHALL use profile-declared Kilo config assets and write the session config to the Kilo project config target.

#### Scenario: Kilo UI shell session starts
- **WHEN** a Kilo UI shell session is prepared
- **THEN** the session security config MUST be written to `.kilo/kilo.jsonc`
- **AND** the enforced layer MUST deny permissions for the UI shell session
- **AND** OpenCode UI shell config paths MUST NOT be used as Kilo targets
