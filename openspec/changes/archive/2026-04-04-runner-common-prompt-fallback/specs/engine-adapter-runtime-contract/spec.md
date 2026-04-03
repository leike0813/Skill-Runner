## MODIFIED Requirements

### Requirement: Skill entrypoint prompts support a common fallback

Runtime prompt resolution MUST allow `runner.json.entrypoint.prompts.common` to act as the default prompt when the current engine does not have an explicit prompt entry.

#### Scenario: Engine-specific prompt still wins

- **GIVEN** a skill manifest with both `entrypoint.prompts.gemini` and `entrypoint.prompts.common`
- **WHEN** the Gemini adapter renders the prompt
- **THEN** the runtime MUST use `entrypoint.prompts.gemini`

#### Scenario: Common prompt is used as default

- **GIVEN** a skill manifest with `entrypoint.prompts.common`
- **AND** no prompt entry for the current engine
- **WHEN** an adapter renders the prompt
- **THEN** the runtime MUST use `entrypoint.prompts.common`
- **AND** only fall back to adapter template assets when `common` is absent
