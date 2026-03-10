## ADDED Requirements

### Requirement: FCMP MUST expose generic assistant process events before final convergence
系统 MUST 支持在 FCMP 中发布通用过程事件（非引擎专属）并在收敛时发布 promoted/final。

#### Scenario: process-first then final
- **GIVEN** engine 在同一回合输出多条中间消息
- **WHEN** runtime 处理该回合流式输出
- **THEN** 系统 MUST 先发布 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`（按实际类型）
- **AND** 在回合结束信号到达后发布 `assistant.message.promoted` 与 `assistant.message.final`

### Requirement: failed/canceled MUST NOT fallback promote assistant final
The runtime MUST NOT emit fallback `assistant.message.final` when status is `failed` or `canceled`.

#### Scenario: failed terminal without turn-end signal
- **GIVEN** run 终态为 `failed` 或 `canceled`
- **AND** 没有可用于收敛的回合结束信号
- **WHEN** FCMP 生成终态事件
- **THEN** 系统 MUST NOT 通过 fallback 生成 `assistant.message.final`
