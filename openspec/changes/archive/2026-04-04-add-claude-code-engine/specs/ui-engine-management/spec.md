## MODIFIED Requirements

### Requirement: UI engine management exposes Claude

The management UI SHALL expose `claude` as a standard engine row.

#### Scenario: Render engine table

- **WHEN** `/ui/engines` or the engines table partial is rendered
- **THEN** Claude MUST appear in the engine list when supported
- **AND** Claude MUST provide install/upgrade, auth entry, and model-management affordances

### Requirement: UI auth metadata is data-driven

Engine auth labels and input hints SHALL be driven by metadata rather than hardcoded template branches per engine.

#### Scenario: Add a new engine

- **WHEN** a new engine such as `claude` is introduced
- **THEN** templates and scripts MUST consume centralized engine UI metadata
- **AND** they MUST not require a new dedicated engine-specific conditional branch in the page template
