## ADDED Requirements

### Requirement: oauth_proxy MUST 支持 Gemini Browser OAuth 组合
系统 MUST 放行以下 start 参数组合：

- `engine=gemini`
- `transport=oauth_proxy`
- `auth_method=browser-oauth`

#### Scenario: 启动 Gemini OAuth 代理会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含上述组合
- **THEN** 返回 `200`
- **AND** 返回会话 `status=waiting_user`
- **AND** 返回可打开的 Google OAuth `auth_url`

#### Scenario: Gemini oauth_proxy 非法组合被拒绝
- **WHEN** `engine=gemini` 且参数组合不在允许集合
- **THEN** 返回 `422`

### Requirement: Gemini oauth_proxy MUST 支持统一 input 手工兜底
系统 MUST 允许会话通过 `/input` 提交完整 redirect URL 或 code。

#### Scenario: 提交完整回调 URL
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions/{session_id}/input`
- **AND** `kind=text`
- **AND** `value` 为完整 redirect URL（含 `code`）
- **THEN** 系统解析并继续 token exchange

#### Scenario: 提交授权码
- **WHEN** `kind=text` 或 `kind=code`
- **AND** `value` 为授权码
- **THEN** 系统使用会话内 state 完成 exchange
