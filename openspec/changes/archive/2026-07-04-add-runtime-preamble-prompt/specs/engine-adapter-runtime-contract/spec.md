## ADDED Requirements

### Requirement: Runtime preamble MUST be injected only into the initial attempt prompt
Adapters SHALL inject client preamble text through the common prompt builder only for the first initial attempt.

#### Scenario: First attempt prompt
- **WHEN** attempt number is `1` and the run has a raw preamble secret
- **THEN** the rendered prompt MUST include a bounded client preamble section after the skill invoke line and before the skill body
- **AND** the section MUST state that it does not override service, engine, skill, safety, or output schema instructions

#### Scenario: Resume and repair prompts
- **WHEN** a prompt is rendered for an interaction reply, auth resume, recovery resume, retry attempt, or output repair
- **THEN** the runtime preamble MUST NOT be injected again
- **AND** internal `__prompt_override` MUST continue to replace the full effective prompt
