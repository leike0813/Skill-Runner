## ADDED Requirements

### Requirement: Engine 鉴权 API MUST 提供 transport 分组路由
系统 MUST 提供按 transport 分组的鉴权会话 API，以避免 `oauth_proxy` 与 `cli_delegate` 契约混淆。

#### Scenario: 启动 oauth_proxy 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/oauth-proxy/sessions`
- **THEN** 系统创建 `oauth_proxy` 会话并返回快照
- **AND** 快照包含 `transport=oauth_proxy`

#### Scenario: 启动 cli_delegate 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/cli-delegate/sessions`
- **THEN** 系统创建 `cli_delegate` 会话并返回快照
- **AND** 快照包含 `transport=cli_delegate`

### Requirement: 回调接口 MUST 归属 oauth_proxy 路由组
系统 MUST 提供 `oauth_proxy` 专属 OpenAI callback 接口，并对 state 执行会话绑定、TTL 与一次性消费校验。

#### Scenario: 有效 state 回调成功
- **WHEN** 客户端访问 `GET /v1/engines/auth/oauth-proxy/callback/openai`
- **AND** `state/code` 匹配活跃会话
- **THEN** 会话推进到成功或明确失败终态

### Requirement: 旧鉴权会话接口 MUST 提供兼容层并标记 deprecated
系统 MUST 保留旧 `/v1/engines/auth/sessions*` 接口一个过渡周期，并显式标记为 deprecated。

#### Scenario: 旧接口启动会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **THEN** 系统通过兼容映射转发到新分组 API
- **AND** 响应中包含 `deprecated=true`

### Requirement: 鉴权会话 V2 模型 MUST 使用 auth_method/provider_id 替代 method
系统 MUST 在 V2 会话模型中移除 `method` 历史语义，统一使用 `auth_method` 与 `provider_id`。

#### Scenario: V2 启动请求
- **WHEN** 客户端提交 `AuthSessionStartRequestV2`
- **THEN** 请求体要求显式 `transport` 与 `auth_method`
- **AND** `provider_id` 在需要 provider 的引擎场景必填
