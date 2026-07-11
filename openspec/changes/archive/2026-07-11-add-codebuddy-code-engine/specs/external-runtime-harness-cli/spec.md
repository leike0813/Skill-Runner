## ADDED Requirements

### Requirement: Agent harness skill injection includes codebuddy

The external runtime harness MUST derive CodeBuddy skill materialization from its adapter profile and place skills under .codebuddy/skills.

#### Scenario: Harness prepares a CodeBuddy run
- **WHEN** a compatible skill is injected
- **THEN** the skill files appear under .codebuddy/skills/<skill-id> and the root contains CODEBUDDY.md
