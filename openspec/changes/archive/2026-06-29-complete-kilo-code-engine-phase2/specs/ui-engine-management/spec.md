## ADDED Requirements

### Requirement: Kilo auth UI MUST use provider-aware management surfaces
The management UI SHALL expose Kilo auth through the existing provider-aware engine UI.

#### Scenario: Kilo auth providers are listed
- **WHEN** the UI requests engine auth providers
- **THEN** Kilo Gateway MUST appear as `Kilo Gateway`
- **AND** Kilo third-party providers MUST appear with OpenCode-compatible labels and input methods

### Requirement: Kilo Gateway missing credentials MUST NOT make the engine unavailable
Kilo Gateway login state SHALL affect Gateway model auth decisions but SHALL NOT make the Kilo engine installation/status row unavailable.

#### Scenario: Kilo Gateway is not logged in
- **WHEN** Kilo is installed but Gateway credentials are missing
- **THEN** management status MUST still report the Kilo engine as available when the CLI is otherwise usable
- **AND** paid Gateway model execution MAY surface auth-required state
