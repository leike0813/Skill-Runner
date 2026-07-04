## ADDED Requirements

### Requirement: Kilo UI shell MUST use Kilo-local config hardening
Kilo UI shell sessions SHALL use profile-declared Kilo config assets and write the session config to the Kilo project config target.

#### Scenario: Kilo UI shell session starts
- **WHEN** a Kilo UI shell session is prepared
- **THEN** the session security config MUST be written to `.kilo/kilo.jsonc`
- **AND** the enforced layer MUST deny permissions for the UI shell session
- **AND** OpenCode UI shell config paths MUST NOT be used as Kilo targets
