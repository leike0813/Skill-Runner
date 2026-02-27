## ADDED Requirements

### Requirement: iflow oauth_proxy 会话 MUST 遵循 oauth_proxy 状态机
`transport=oauth_proxy, engine=iflow` 会话 MUST 使用 oauth_proxy 状态语义。

#### Scenario: 禁止 waiting_orchestrator
- **WHEN** 会话 `transport=oauth_proxy` 且 `engine=iflow`
- **THEN** 状态不得为 `waiting_orchestrator`

#### Scenario: 允许 code_submitted_waiting_result
- **WHEN** 用户通过 `/input` 提交内容并被接受
- **THEN** 状态可短暂进入 `code_submitted_waiting_result` 后收敛到终态

### Requirement: iflow oauth_proxy MUST 记录 callback/手工路径审计
系统 MUST 区分自动回调与手工兜底路径。

#### Scenario: 自动回调成功
- **WHEN** 本地 listener 收到回调并完成鉴权
- **THEN** `audit.oauth_callback_received=true`
- **AND** `audit.callback_mode="auto"`

#### Scenario: 手工兜底成功
- **WHEN** 用户通过 `/input` 完成鉴权
- **THEN** `audit.manual_fallback_used=true`
- **AND** `audit.callback_mode="manual"`
