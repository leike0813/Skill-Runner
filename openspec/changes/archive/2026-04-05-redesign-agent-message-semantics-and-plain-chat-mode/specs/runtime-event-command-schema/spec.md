## ADDED Requirements

### Requirement: runtime schema MUST accept intermediate agent message events
runtime protocol schema MUST 为非终态 agent 文本提供独立事件合同，并同时支持 FCMP 与 RASP 命名空间中的中间消息事件。

#### Scenario: FCMP intermediate message payload validates
- **WHEN** schema 校验类型为 `assistant.message.intermediate` 的 FCMP 事件
- **THEN** 事件 MUST 通过校验
- **AND** payload MUST 支持 `message_id`、`attempt`、`raw_ref` 等现有消息关联字段

#### Scenario: RASP intermediate message payload validates
- **WHEN** schema 校验类型为 `agent.message.intermediate` 的 RASP 事件
- **THEN** 事件 MUST 通过校验
- **AND** 该合同 MUST 与 `agent.reasoning` / `agent.tool_call` / `agent.command_execution` 并存
