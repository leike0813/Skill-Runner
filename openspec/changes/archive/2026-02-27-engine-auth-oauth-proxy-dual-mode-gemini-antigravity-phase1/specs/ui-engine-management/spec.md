## ADDED Requirements

### Requirement: UI MUST emit unified auth_method values
管理页鉴权入口 MUST 使用 `callback/auth_code_or_url/api_key`，不得再发送历史值。

#### Scenario: Deprecated methods removed in UI
- **WHEN** 用户点击任意鉴权按钮
- **THEN** 请求体中的 `auth_method` 不包含历史值

### Requirement: Gemini oauth_proxy MUST expose dual-mode buttons
管理页 MUST 为 Gemini 的 oauth_proxy 暴露两个并列入口按钮。

#### Scenario: Gemini dual buttons visible
- **WHEN** 用户进入 `/ui/engines`
- **THEN** 页面同时提供：
  - Gemini OAuth 代理（callback）
  - Gemini OAuth 代理（auth_code_or_url）

### Requirement: OpenCode Google oauth_proxy MUST expose dual-mode buttons
管理页 MUST 为 OpenCode Google 的 oauth_proxy 暴露两个并列入口按钮。

#### Scenario: OpenCode Google dual buttons visible
- **WHEN** 用户进入 `/ui/engines`
- **THEN** 页面同时提供：
  - OpenCode(Google) OAuth 代理（callback）
  - OpenCode(Google) OAuth 代理（auth_code_or_url）
