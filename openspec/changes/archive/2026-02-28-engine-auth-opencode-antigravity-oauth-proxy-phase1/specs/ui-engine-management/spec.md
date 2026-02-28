## ADDED Requirements

### Requirement: Engine 管理页 MUST 提供 OpenCode Google OAuth 代理独立入口
系统 MUST 在 `/ui/engines` 提供可直接触发 `opencode+google+oauth_proxy+browser-oauth` 的按钮。

#### Scenario: 点击按钮启动会话
- **WHEN** 用户点击 OpenCode Google OAuth 代理按钮
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含：
  - `engine=opencode`
  - `transport=oauth_proxy`
  - `provider_id=google`
  - `auth_method=browser-oauth`

### Requirement: UI MUST 支持自动回调与手工输入双模式协同
系统 MUST 在同一会话中同时支持自动回调与手工输入兜底，不要求用户区分链路。

#### Scenario: 自动回调成功
- **WHEN** 本地 listener 已接收回调并完成 exchange
- **THEN** UI 轮询状态进入 `succeeded`

#### Scenario: 自动回调不可达时手工兜底
- **WHEN** 用户将回调 URL 或 code 粘贴到输入框并提交
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions/{id}/input`
- **AND** 成功后会话收口到终态

### Requirement: 现有 OpenCode Google CLI 委托入口 MUST 保持不变
系统 MUST 保留并维持现有 `cli_delegate` Google 按钮与行为。

#### Scenario: CLI 委托入口不受影响
- **WHEN** 用户选择 OpenCode Google CLI 委托入口
- **THEN** 流程与本 change 之前保持一致
