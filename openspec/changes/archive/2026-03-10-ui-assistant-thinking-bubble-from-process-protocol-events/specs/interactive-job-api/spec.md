## ADDED Requirements

### Requirement: chat history API MUST expose assistant process rows for FCMP process events
系统 MUST 将 FCMP 的 assistant 过程事件映射为 chat history 可消费条目，且不新增路由。

#### Scenario: process events in chat history
- **GIVEN** FCMP 流包含 `assistant.reasoning`、`assistant.tool_call`、`assistant.command_execution`
- **WHEN** 客户端读取 `/chat/history`
- **THEN** 返回事件 MUST 包含 `role=assistant` 且 `kind=assistant_process` 的条目
- **AND** 条目 SHOULD 在 correlation 中包含 `process_type`、`message_id`（若有）与 `fcmp_seq`

### Requirement: promoted event MUST NOT be rendered as standalone chat body
系统 MUST NOT 将 `assistant.message.promoted` 导出为独立聊天正文条目。

#### Scenario: promoted boundary only
- **GIVEN** FCMP 流包含 `assistant.message.promoted`
- **WHEN** 生成 chat replay 历史
- **THEN** 该事件 MUST 仅作为收敛边界语义使用
- **AND** MUST NOT 生成额外聊天正文文本条目
