## ADDED Requirements

### Requirement: process events MUST NOT mutate canonical session states
Process events SHALL NOT mutate canonical state transitions.

#### Scenario: publishing reasoning/tool/command events
- **GIVEN** run 正处于任一非终态
- **WHEN** 系统发布 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`
- **THEN** canonical conversation state MUST remain unchanged

### Requirement: fallback promotion guard by target state
Fallback promotion MUST be state-gated by target status.

#### Scenario: fallback promotion state gate
- **GIVEN** 系统需要对可提升消息执行 fallback
- **WHEN** target status is `succeeded` or `waiting_user`
- **THEN** fallback promotion MAY execute
- **AND** when target status is `failed` or `canceled`, fallback promotion MUST NOT execute
