## ADDED Requirements

### Requirement: strict replay evidence MUST preserve uploads-relative file references
The runtime audit and rebuild contract MUST preserve enough information to replay declarative file-input references and resolved artifact paths.

#### Scenario: request payload records declarative file input
- **WHEN** a run is created with file input paths in the request body
- **THEN** the request snapshot preserves those values for audit and rebuild purposes
