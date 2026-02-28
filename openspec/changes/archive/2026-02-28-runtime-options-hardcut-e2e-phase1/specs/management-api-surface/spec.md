## ADDED Requirements

### Requirement: Runtime options contract MUST use hard-cut keys
`/v1/jobs*` 与 `/v1/temp-skill-runs*` 的 `runtime_options` MUST 采用新键集合，旧键不再兼容。

#### Scenario: Submit request with removed runtime option keys
- **WHEN** 客户端提交 `verbose`、`session_timeout_sec`、`interactive_wait_timeout_sec`、`hard_wait_timeout_sec`、`wait_timeout_sec` 或 `interactive_require_user_reply`
- **THEN** 服务返回 `422`（或参数校验错误）
- **AND** 不进行自动映射或静默忽略

#### Scenario: Submit request with new interactive keys
- **WHEN** 客户端提交 `interactive_auto_reply` 与 `interactive_reply_timeout_sec`
- **THEN** 服务按新语义接受并执行
- **AND** `interactive_auto_reply` 默认值为 `false`

### Requirement: Interactive timeout semantics MUST align with interactive_auto_reply
interactive waiting 超时触发逻辑 MUST 由 `interactive_auto_reply` 控制。

#### Scenario: interactive_auto_reply enabled
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=true` 且进入 waiting_user
- **THEN** 在 `interactive_reply_timeout_sec` 到达后触发自动回复续跑

#### Scenario: interactive_auto_reply disabled
- **WHEN** `execution_mode=interactive` 且 `interactive_auto_reply=false`
- **THEN** 超时不触发自动回复
- **AND** 会话持续等待用户回复
