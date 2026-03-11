## ADDED Requirements

### Requirement: jobs artifact single-file download MUST be retired
The public jobs API MUST NOT expose a dedicated single-artifact download route once artifact paths are contract-driven.

#### Scenario: client downloads artifacts through bundle only
- **WHEN** a client needs terminal artifacts
- **THEN** it uses bundle or debug bundle download
- **AND** no single-artifact jobs route is required
