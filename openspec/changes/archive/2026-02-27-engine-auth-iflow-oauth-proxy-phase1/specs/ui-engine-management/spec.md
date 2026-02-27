## ADDED Requirements

### Requirement: Engine 管理页 MUST 提供 iFlow OAuth 代理双入口
系统 MUST 在 `/ui/engines` 同时展示：

1. `iFlow OAuth代理（Callback）`
2. `iFlow OAuth代理（AuthCode/URL）`

且保留现有 `iFlow CLI委托` 入口。

#### Scenario: 点击 iFlow OAuth 代理 Callback 按钮
- **WHEN** 用户点击 `iFlow OAuth代理（Callback）`
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions`
- **AND** 请求参数 `engine=iflow, transport=oauth_proxy, auth_method=callback`

#### Scenario: 点击 iFlow OAuth 代理 AuthCode/URL 按钮
- **WHEN** 用户点击 `iFlow OAuth代理（AuthCode/URL）`
- **THEN** UI 调用 `/ui/engines/auth/oauth-proxy/sessions`
- **AND** 请求参数 `engine=iflow, transport=oauth_proxy, auth_method=auth_code_or_url`

### Requirement: iFlow OAuth 代理输入提示 MUST 明确 URL/code 双支持
在 iFlow OAuth 代理会话等待用户输入时，UI MUST 明确提示可提交“授权码或回调 URL”。

#### Scenario: iFlow oauth_proxy waiting_user
- **WHEN** 当前会话 `engine=iflow, transport=oauth_proxy, status=waiting_user`
- **THEN** 输入区可见
- **AND** 文案提示可提交授权码或回调 URL
