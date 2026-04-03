## MODIFIED Requirements

### Requirement: ui shell governance is profile-first

The adapter runtime contract SHALL define `ui_shell` capability and security metadata in adapter profiles.

#### Scenario: capability metadata is loaded from profile

- **WHEN** the system constructs a `ui_shell` capability for an engine
- **THEN** it MUST read command id, label, trust bootstrap behavior, sandbox retry behavior, probe strategy, auth hint strategy, and config asset locations from the adapter profile
- **AND** it MUST NOT hardcode those values per engine in the capability provider

#### Scenario: session-local ui shell config is generated from engine assets

- **WHEN** an engine requires a session-local `ui_shell` config file
- **THEN** the system MUST compose it from engine-owned `ui_shell` config assets plus runtime overrides
- **AND** it MUST NOT hand-assemble the full config payload in the capability provider
