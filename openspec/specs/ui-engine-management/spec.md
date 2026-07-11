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
## Requirements

### Requirement: CodeBuddy management UI MUST expose provider-specific auth controls

The UI MUST display installation/version status and separate domestic and global login, relogin, and clear-credential actions using redacted provider states.

#### Scenario: Only domestic credential exists
- **WHEN** the CodeBuddy management detail is rendered
- **THEN** domestic shows present/relogin/clear and global shows login
### Requirement: CodeBuddy inline TUI MUST require an explicit authenticated provider

Engine shell capability discovery MUST expose CodeBuddy TUI. Starting it MUST require an explicit canonical provider with credential state present. Missing, expired, or invalid provider selection MUST fail closed without spawning a process.

#### Scenario: CodeBuddy TUI action is selected
- **WHEN** the operator clicks the CodeBuddy inline-terminal action
- **THEN** the UI opens a provider picker derived from `engineAuthProviders.codebuddy` with no initial selection

#### Scenario: Provider is not authenticated
- **WHEN** a missing or expired provider is displayed
- **THEN** only login or relogin is available and the terminal cannot start

#### Scenario: Authentication completes
- **WHEN** provider status refreshes to present after login
- **THEN** the operator must explicitly select and confirm terminal launch; the UI does not auto-launch
### Requirement: Management UI MUST remain an administration-only surface

The management UI MUST NOT add a CodeBuddy job launcher, job form partial, or internal job-creation route. Existing engine status, credentials, install/upgrade, and capability-gated shell controls remain available.

#### Scenario: CodeBuddy engine detail loads
- **WHEN** an operator views CodeBuddy management details
- **THEN** credential and engine controls are shown without any job creation action

