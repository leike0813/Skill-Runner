## MODIFIED Requirements

### Requirement: Management UI engine page supports custom-provider CRUD

The engine management UI SHALL expose custom-provider CRUD for engines that register this capability.

#### Scenario: render Claude custom providers

- **WHEN** `/ui/engines` renders Claude engine management data
- **THEN** the page MUST show a custom-provider configuration area for Claude
- **AND** it MUST support list, create, update, and delete
- **AND** it MUST not expose the same full CRUD surface inside the run form
