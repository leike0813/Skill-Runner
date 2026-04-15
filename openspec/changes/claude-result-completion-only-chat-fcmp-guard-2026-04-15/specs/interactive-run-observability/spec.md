## ADDED Requirements

### Requirement: Claude result fallback messages MUST be explicitly sourced

运行时观测层在使用 Claude `result.result` 作为 fallback assistant message 时 MUST 保留明确来源标记，
避免与正常 assistant body text 混淆。

#### Scenario: Claude result fallback reaches runtime observability

- **GIVEN** Claude 当前 turn 没有真实 assistant body message
- **AND** `result.result` 被接受为 fallback assistant message
- **WHEN** runtime 发布对应 RASP / FCMP 中间消息与 final 消息
- **THEN** 消息 `details.source` MUST 等于 `claude_result_fallback`
- **AND** completion metadata 仍 MUST 继续通过 turn-complete 语义发布
