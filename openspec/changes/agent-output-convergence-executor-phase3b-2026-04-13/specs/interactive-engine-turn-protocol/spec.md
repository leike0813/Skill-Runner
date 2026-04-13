## ADDED Requirements

### Requirement: Interactive Prompt Contract Uses JSON Pending or Final Branches

Interactive engine prompts MUST instruct the agent to emit the JSON union contract only.

#### Scenario: Pending-turn guidance forbids legacy ask-user blocks
- **WHEN** runtime patches a skill for interactive execution
- **THEN** the prompt MUST instruct the agent to emit either:
  - a final JSON object with `__SKILL_DONE__ = true`, or
  - a pending JSON object with `__SKILL_DONE__ = false`, `message`, and `ui_hints`
- **AND** the prompt MUST explicitly forbid `<ASK_USER_YAML>` as a valid output protocol
