## ADDED Requirements

### Requirement: Auth method MUST use unified semantics
系统 MUST 仅接受以下 `auth_method`：

1. `callback`
2. `auth_code_or_url`
3. `api_key`

#### Scenario: Legacy auth_method rejected
- **WHEN** 请求携带历史值（`browser-oauth/device-auth/screen-reader-google-oauth/iflow-cli-oauth/opencode-provider-auth`）
- **THEN** 返回 `422`

### Requirement: Gemini oauth_proxy MUST support dual modes
系统 MUST 同时支持 `callback` 与 `auth_code_or_url` 两种 `oauth_proxy` 模式。

#### Scenario: Gemini callback
- **WHEN** `engine=gemini, transport=oauth_proxy, auth_method=callback`
- **THEN** 会话可启动且不接受 `/input`

#### Scenario: Gemini auth_code_or_url
- **WHEN** `engine=gemini, transport=oauth_proxy, auth_method=auth_code_or_url`
- **THEN** 会话可启动且支持 `/input(kind=code|text)`

### Requirement: OpenCode Google oauth_proxy MUST support dual modes
系统 MUST 同时支持 `callback` 与 `auth_code_or_url` 两种 `oauth_proxy` 模式。

#### Scenario: OpenCode Google callback
- **WHEN** `engine=opencode, provider_id=google, transport=oauth_proxy, auth_method=callback`
- **THEN** 会话可启动且不接受 `/input`

#### Scenario: OpenCode Google auth_code_or_url
- **WHEN** `engine=opencode, provider_id=google, transport=oauth_proxy, auth_method=auth_code_or_url`
- **THEN** 会话可启动且支持 `/input(kind=text|code)`
