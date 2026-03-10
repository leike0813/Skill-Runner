## ADDED Requirements

### Requirement: RASP MUST provide engine-agnostic process event types
RASP 审计层 MUST 使用通用 `agent.*` 过程事件类型，不得引入 engine-specific 顶层事件名。

#### Scenario: parser emits process semantics
- **GIVEN** parser 识别到推理、工具调用或命令执行
- **WHEN** RASP 事件发布
- **THEN** 系统 MUST 使用 `agent.reasoning` / `agent.tool_call` / `agent.command_execution`
- **AND** MUST NOT 使用引擎专属 type 名称进入 runtime contract

### Requirement: promoted MUST precede final for same message_id
The system MUST publish `agent.message.promoted` before `agent.message.final` for the same `message_id`.

#### Scenario: message promotion for final answer
- **GIVEN** 存在可提升消息 `message_id=X`
- **WHEN** 系统发布最终收敛事件
- **THEN** `agent.message.promoted(message_id=X)` MUST precede `agent.message.final(message_id=X)`
