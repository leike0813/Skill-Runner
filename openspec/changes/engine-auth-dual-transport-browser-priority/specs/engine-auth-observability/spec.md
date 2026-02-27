## ADDED Requirements

### Requirement: 会话快照 MUST 暴露 auth_method 可观测字段
系统 MUST 在 auth session snapshot 中返回 `auth_method`。

#### Scenario: status 查询
- **WHEN** 客户端查询会话状态
- **THEN** 响应包含 `transport`
- **AND** 响应包含 `auth_method`
- **AND** 响应包含 `execution_mode`

### Requirement: waiting_orchestrator MUST 仅用于 CLI 委托路径
系统 MUST 将 `waiting_orchestrator` 限制在 `cli_delegate` 的自动操作阶段。

#### Scenario: oauth_proxy 路径
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 状态不得为 `waiting_orchestrator`

#### Scenario: cli_delegate 路径
- **WHEN** 会话 `transport=cli_delegate`
- **THEN** 允许 `waiting_orchestrator` 表示后端自动输入进行中

### Requirement: browser callback 与 manual fallback MUST 可审计
系统 MUST 在 snapshot 中区分自动回调与手工兜底。

#### Scenario: callback 自动成功
- **WHEN** browser callback 成功
- **THEN** `oauth_callback_received=true`
- **AND** `oauth_callback_at` 为有效时间戳
- **AND** `manual_fallback_used=false`

#### Scenario: 手工 input 完成
- **WHEN** 用户通过 `/input` 完成授权闭环
- **THEN** `manual_fallback_used=true`

### Requirement: device-auth 协议阶段 MUST 可观测
系统 MUST 在 device-auth 会话中提供用户可操作信息。

#### Scenario: waiting_user with device code
- **WHEN** 会话为 `auth_method=device-auth` 且 `status=waiting_user`
- **THEN** snapshot 包含可访问的 `auth_url`（verification URL）
- **AND** `user_code` 可见
