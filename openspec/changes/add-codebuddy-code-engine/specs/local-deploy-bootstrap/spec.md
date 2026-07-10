## ADDED Requirements

### Requirement: Local bootstrap MUST prepare CodeBuddy managed storage

Local deployment bootstrap MUST make CodeBuddy credential, provider config, and provider model-cache roots available with owner-only permissions where secrets or session state can be stored.

#### Scenario: A fresh local deployment starts
- **WHEN** CodeBuddy has not previously been used
- **THEN** first use yields deterministic data-dir and agent-home paths without reading host CodeBuddy state
