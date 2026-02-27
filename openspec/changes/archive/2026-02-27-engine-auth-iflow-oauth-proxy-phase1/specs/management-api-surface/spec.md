## ADDED Requirements

### Requirement: oauth_proxy MUST 支持 iflow 双模式
系统 MUST 放行以下 start 参数组合：

- `engine=iflow`
- `transport=oauth_proxy`
- `auth_method=callback | auth_code_or_url`

#### Scenario: 启动 iflow callback 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions`
- **AND** 请求体包含 `engine=iflow, transport=oauth_proxy, auth_method=callback`
- **THEN** 返回 `200`
- **AND** 会话进入 `waiting_user`
- **AND** 返回可打开的 `auth_url`

#### Scenario: 启动 iflow 手工码流会话
- **WHEN** 请求体包含 `engine=iflow, transport=oauth_proxy, auth_method=auth_code_or_url`
- **THEN** 返回 `200`
- **AND** 会话进入 `waiting_user`

### Requirement: iflow callback 模式 MUST 支持 input 兜底
系统 MUST 在 callback 模式中保留 `/input` 兜底能力（URL 或 code）。

#### Scenario: callback listener 不可用时手工完成
- **WHEN** 会话已启动但本地回调不可达
- **AND** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions/{session_id}/input`
- **THEN** 系统可继续 token exchange 并收敛到终态

### Requirement: iflow oauth_proxy MUST 保持 auth-status 兼容写盘
系统 MUST 在鉴权成功后写入 auth-status 所依赖的 iflow 认证文件集合。

#### Scenario: 成功后 auth-ready 可被现有逻辑识别
- **WHEN** iflow oauth_proxy 会话成功
- **THEN** `.iflow/oauth_creds.json` 存在
- **AND** `.iflow/iflow_accounts.json` 存在
- **AND** `.iflow/settings.json` 满足 `selectedAuthType=oauth-iflow` 且 `baseUrl` 有效
