## ADDED Requirements

### Requirement: oauth_proxy MUST 支持 OpenCode Google Browser OAuth 组合
系统 MUST 放行以下 start 参数组合：

- `engine=opencode`
- `transport=oauth_proxy`
- `provider_id=google`
- `auth_method=browser-oauth`

#### Scenario: 启动 OpenCode Google OAuth 代理会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含上述组合
- **THEN** 返回 `200` 且会话进入 `waiting_user`
- **AND** 返回可打开的 Google OAuth `auth_url`

#### Scenario: 非法组合被拒绝
- **WHEN** `engine=opencode` 且 `transport=oauth_proxy` 但参数组合不在允许集合
- **THEN** 返回 `422`

### Requirement: OpenCode Google oauth_proxy MUST 支持手工输入兜底
系统 MUST 允许会话通过统一 input 接口回填完整 redirect URL 或 code。

#### Scenario: 提交完整回调 URL
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions/{session_id}/input`
- **AND** `kind=text`
- **AND** `value` 为完整回调 URL（含 `code`）
- **THEN** 系统解析并继续 token exchange

#### Scenario: 提交授权码
- **WHEN** `kind=text`
- **AND** `value` 为 code
- **THEN** 系统使用会话内 state 完成 exchange
