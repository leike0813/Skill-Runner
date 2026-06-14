## MODIFIED Requirements

### Requirement: Refresh skill registry after successful install
After a successful install or update, the system SHALL make the skill available to discovery without requiring a server restart and refresh its normalized package identity.

#### Scenario: Post-install discovery and package identity refresh
- **WHEN** an install job completes successfully
- **THEN** the skill appears in skill discovery results
- **AND** the installed skill's normalized package hash is recorded for cache key computation

### Requirement: Installed skill package identity MUST refresh on startup
The system MUST refresh normalized package identity for registry-visible installed and builtin skills during service startup.

#### Scenario: Startup identity refresh
- **WHEN** the service starts
- **THEN** registry-visible skill directories are scanned
- **AND** each valid skill's normalized package hash is recorded
