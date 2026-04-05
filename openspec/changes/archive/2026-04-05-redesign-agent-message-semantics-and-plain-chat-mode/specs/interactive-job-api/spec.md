## MODIFIED Requirements

### Requirement: FCMP MUST expose generic assistant process events before final convergence
系统 MUST 支持在 FCMP 中发布通用过程事件（非引擎专属），并将非终态 agent 文本作为独立消息语义发布；在收敛时继续发布 promoted/final 边界。

#### Scenario: process and intermediate message before final
- **GIVEN** engine 在同一回合输出真正的过程事件与面向用户的非终态 agent 文本
- **WHEN** runtime 处理该回合流式输出
- **THEN** 系统 MUST 先发布 `assistant.reasoning` / `assistant.tool_call` / `assistant.command_execution`（按实际类型）
- **AND** 对非终态 agent 文本 MUST 发布 `assistant.message.intermediate`
- **AND** 在回合结束信号到达后继续发布 `assistant.message.promoted` 与 `assistant.message.final`

### Requirement: chat history API MUST expose assistant process rows for FCMP process events
系统 MUST 将 FCMP 的 assistant 过程事件映射为 chat history 可消费条目，并将非终态 agent message 映射为独立聊天条目，且不新增路由。

#### Scenario: process events and intermediate messages in chat history
- **GIVEN** FCMP 流包含 `assistant.reasoning`、`assistant.tool_call`、`assistant.command_execution` 与 `assistant.message.intermediate`
- **WHEN** 客户端读取 `/chat/history`
- **THEN** 过程事件返回条目 MUST 包含 `role=assistant` 且 `kind=assistant_process`
- **AND** 中间消息返回条目 MUST 包含 `role=assistant` 且 `kind=assistant_message`
- **AND** 条目 SHOULD 在 correlation 中包含 `process_type`、`message_id`（若有）与 `fcmp_seq`

### Requirement: promoted event MUST NOT be rendered as standalone chat body
系统 MUST NOT 将 `assistant.message.promoted` 导出为独立聊天正文条目；它只表达收敛边界，不负责把正文从过程语义中补救出来。

#### Scenario: promoted boundary only
- **GIVEN** FCMP 流包含 `assistant.message.intermediate` 与后续 `assistant.message.promoted`
- **WHEN** 生成 chat replay 历史
- **THEN** `assistant.message.promoted` MUST 仅作为收敛边界语义使用
- **AND** MUST NOT 额外生成新的聊天正文文本条目
- **AND** 现有 `assistant.message.intermediate` 条目身份 MUST 保持稳定
