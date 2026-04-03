## MODIFIED Requirements

### Requirement: Container Assets Include Required Engine Runtime Dependencies

Containerized deployment assets MUST include the dependencies needed for supported engine runtime features.

#### Scenario: Claude sandbox dependencies are present in the runtime image
- **WHEN** the runtime image is built for container deployment
- **THEN** the image MUST include `bubblewrap` and `socat`
- **AND** deployment documentation MUST state that these dependencies are required for Claude sandbox support

#### Scenario: Missing Claude sandbox dependencies stay warning-only
- **WHEN** Claude sandbox dependencies are unavailable in a local or nonstandard runtime
- **THEN** diagnostics MUST warn clearly about the missing dependencies
- **AND** the system MUST NOT convert that condition into a hard bootstrap or preflight failure by itself
