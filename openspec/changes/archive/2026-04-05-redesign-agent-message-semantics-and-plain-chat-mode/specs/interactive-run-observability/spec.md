## MODIFIED Requirements

### Requirement: RASP MUST provide engine-agnostic process event types
RASP 审计层 MUST 使用通用 `agent.*` 过程事件类型表达真正的推理、工具调用与命令执行，并使用独立消息语义表达非终态 agent 文本；不得引入 engine-specific 顶层事件名。

#### Scenario: parser emits process semantics and non-final agent text
- **GIVEN** parser 同时识别到推理、工具调用、命令执行和面向用户的非终态 agent 文本
- **WHEN** RASP 事件发布
- **THEN** 系统 MUST 使用 `agent.reasoning` / `agent.tool_call` / `agent.command_execution` 表达真正过程语义
- **AND** 对非终态 agent 文本 MUST 使用 `agent.message.intermediate`
- **AND** MUST NOT 使用引擎专属 type 名称进入 runtime contract

### Requirement: promoted MUST precede final for same message_id
The system MUST publish `agent.message.promoted` before `agent.message.final` for the same `message_id`，且 promoted/final 只表达收敛边界，不重新定义中间消息的原始语义。

#### Scenario: intermediate message converges to final answer
- **GIVEN** 已存在一条 `agent.message.intermediate(message_id=X)`
- **WHEN** 系统发布最终收敛事件
- **THEN** `agent.message.promoted(message_id=X)` MUST precede `agent.message.final(message_id=X)`
- **AND** `agent.message.intermediate` MUST NOT 被重新归类为 `agent.reasoning`
