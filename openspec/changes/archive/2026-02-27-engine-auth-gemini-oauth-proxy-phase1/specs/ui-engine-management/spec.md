## ADDED Requirements

### Requirement: Engine 管理页 MUST 提供 Gemini OAuth 代理独立入口
系统 MUST 在 `/ui/engines` 提供可直接触发 `gemini+oauth_proxy+browser-oauth` 的按钮，并与 Gemini CLI 委托入口并行展示。

#### Scenario: 点击 Gemini OAuth 代理按钮
- **WHEN** 用户点击 Gemini OAuth 代理按钮
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含：
  - `engine=gemini`
  - `transport=oauth_proxy`
  - `auth_method=browser-oauth`

### Requirement: UI MUST 支持 Gemini oauth_proxy 自动回调与手工兜底
系统 MUST 在同一会话中允许自动回调成功或用户手工输入 fallback 成功。

#### Scenario: 自动回调成功
- **WHEN** 本地 listener 成功收到回调
- **THEN** UI 轮询状态进入 `succeeded`

#### Scenario: 自动回调不可达时手工兜底
- **WHEN** 用户在输入框提交 redirect URL 或 code
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions/{id}/input`
- **AND** 会话可继续收敛到终态

### Requirement: 本期 MUST 不引入 mcp-oauth-tokens-v2 写入 UI 语义
系统 MUST 不在 UI 文案或交互中暴露 `mcp-oauth-tokens-v2.json` 读写语义。

#### Scenario: Gemini OAuth 代理成功后展示
- **WHEN** 会话成功
- **THEN** UI 仅展示会话终态与错误/提示信息
- **AND** 不展示/不要求用户处理 `mcp-oauth-tokens-v2.json`
