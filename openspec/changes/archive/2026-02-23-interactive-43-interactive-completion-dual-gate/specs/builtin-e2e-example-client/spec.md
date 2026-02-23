## MODIFIED Requirements

### Requirement: 示例客户端 MUST 支持交互式对话直到终态
The example client MUST treat backend lifecycle state as the single source of truth for interaction progression and MUST NOT parse assistant ask_user JSON text as control state.

#### Scenario: waiting_user 时从 pending 驱动 reply
- **WHEN** 运行进入 `waiting_user`
- **THEN** 客户端通过 pending 接口获取 `interaction_id/prompt`
- **AND** 用户提交 reply 后继续推进运行

#### Scenario: assistant ask_user 文本不驱动状态机
- **WHEN** assistant 消息包含 ask_user-like JSON 文本
- **THEN** 客户端仅将其展示在对话区
- **AND** 不把其当作 reply 表单数据来源

#### Scenario: 客户端展示软完成告警
- **WHEN** interactive run 通过“无 done marker 但 schema 通过”完成
- **THEN** 客户端展示 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER` 诊断信息

#### Scenario: 客户端展示 max_attempt 失败原因
- **WHEN** interactive run 达到 `max_attempt` 且无完成证据
- **THEN** 客户端展示 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED` 失败原因
