## ADDED Requirements

### Requirement: Qwen live observability MUST use shared run-handle and process-event semantics
Qwen 的 live observability 要求 MUST 归入共享 `interactive-run-observability` capability，而不是通过独立 qwen parser capability 单独维护。

#### Scenario: qwen init event emits run handle
- **GIVEN** Qwen 输出 `system/subtype=init` 且包含 `session_id`
- **WHEN** live parser 与 publisher 处理该事件
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** `data.handle_id` MUST 等于该 `session_id`

#### Scenario: qwen process semantics use shared agent event types
- **GIVEN** Qwen 解析到 `thinking`、`tool_use` 或 `tool_result`
- **WHEN** 这些语义进入 RASP/FCMP 可观测链路
- **THEN** `thinking` MUST 使用共享 `agent.reasoning`
- **AND** `run_shell_command` MUST 使用共享 `agent.command_execution`
- **AND** 其它 Qwen tools MUST 使用共享 `agent.tool_call`
