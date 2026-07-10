## ADDED Requirements

### Requirement: Skill manifests MAY target codebuddy

The skill manifest schema MUST accept codebuddy in supported and unsupported engine declarations and runtime validation MUST use the same active-engine vocabulary.

#### Scenario: Skill explicitly supports CodeBuddy
- **WHEN** a manifest contains engines with codebuddy
- **THEN** schema validation succeeds and the skill can be selected for a CodeBuddy job
