## ADDED Requirements

### Requirement: 系统 MUST 提供鉴权会话状态可观测语义
系统 MUST 为 device-auth 会话提供稳定状态集和字段语义，供 UI 与 API 统一消费。

#### Scenario: 查询会话状态快照
- **WHEN** 客户端查询会话状态
- **THEN** 响应包含 `session_id`、`engine`、`status`、`expires_at`
- **AND** 状态值属于 `starting|waiting_user|succeeded|failed|canceled|expired`

#### Scenario: 会话 challenge 可见
- **WHEN** 会话进入 `waiting_user`
- **THEN** 若解析到 challenge，响应包含 `auth_url` 与 `user_code`
- **AND** 未解析到 challenge 时返回 `null` 并提供错误摘要字段

### Requirement: 鉴权完成后 auth-status MUST 一致联动
系统 MUST 保证会话终态与 `GET /v1/engines/auth-status` 的 `auth_ready` 语义一致。

#### Scenario: 鉴权成功联动
- **WHEN** Codex device-auth 会话状态为 `succeeded`
- **THEN** `GET /v1/engines/auth-status` 中 `engines.codex.auth_ready` 为 `true`

#### Scenario: 鉴权失败或取消不误报
- **WHEN** 会话状态为 `failed|canceled|expired`
- **THEN** 系统不应将该会话直接视为鉴权成功
- **AND** `auth_ready` 仅由真实凭据状态决定
