## ADDED Requirements

### Requirement: Engine Auth Strategy Must Be Engine-Scoped Configuration

Engine auth strategy capabilities MUST be sourced from engine-scoped strategy files under `server/engines/<engine>/config/` and aggregated by a single strategy service.

#### Scenario: strategy service resolves capabilities from engine files

- **WHEN** UI and orchestration query auth capabilities
- **THEN** both receive data from the same strategy service
- **AND** engine-scoped strategy files are the preferred source
- **AND** legacy global strategy file MAY be used only as migration fallback
