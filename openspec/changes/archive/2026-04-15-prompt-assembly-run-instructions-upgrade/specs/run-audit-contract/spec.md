## ADDED Requirements

### Requirement: First-attempt prompt audit MUST record only the assembled skill prompt
系统 MUST 将 `.audit/request_input.json` 中的 `rendered_prompt_first_attempt` 语义收口为首次实际调用引擎时的最终 assembled skill prompt。

#### Scenario: first-attempt prompt audit
- **WHEN** 第一个 attempt 首次实际调用引擎
- **THEN** `rendered_prompt_first_attempt` MUST 记录最终 assembled prompt
- **AND** 该字段 MUST NOT 隐含 run-root instruction file 的文本内容

#### Scenario: prompt audit fallback
- **WHEN** 系统无法回写 `.audit/request_input.json`
- **THEN** `.audit/prompt.1.txt` MUST 记录同一份 assembled prompt
