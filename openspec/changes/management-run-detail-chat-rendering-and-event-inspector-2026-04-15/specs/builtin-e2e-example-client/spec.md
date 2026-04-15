## MODIFIED Requirements

### Requirement: E2E observe chat MUST share markdown rendering assets with management UI
The built-in E2E observe client MUST consume the same shared chat markdown assets as the management run-detail page.

#### Scenario: E2E renders markdown chat content
- **WHEN** the E2E observe page renders chat messages
- **THEN** it MUST use the shared chat markdown renderer helper
- **AND** it MUST use the shared chat markdown stylesheet
- **AND** it MUST preserve the existing markdown and formula rendering capabilities
