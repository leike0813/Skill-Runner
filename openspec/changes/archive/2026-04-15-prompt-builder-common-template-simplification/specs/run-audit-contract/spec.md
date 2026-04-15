## ADDED Requirements

### Requirement: Prompt audit MUST reflect the simplified assembled prompt contract
系统 MUST 继续将 `.audit/request_input.json.rendered_prompt_first_attempt` 视为最终 assembled skill prompt，但该 prompt 不得再依赖被移除的 prompt-builder compatibility context。

#### Scenario: first-attempt prompt is audited
- **WHEN** 系统记录 first-attempt rendered prompt
- **THEN** 它 MUST reflect invoke-line plus body prompt assembly
- **AND** the body MUST come from either skill-declared body text or the shared default body template with optional profile extra blocks
