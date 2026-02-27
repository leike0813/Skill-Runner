## ADDED Requirements

### Requirement: 引擎鉴权 start 接口 MUST 支持 auth_method 维度
系统 MUST 在 `POST /v1/engines/auth/sessions` 支持可选字段 `auth_method`。

#### Scenario: 新客户端显式传 auth_method
- **WHEN** 请求包含 `auth_method`
- **THEN** 服务按 `(engine, transport, method, provider_id, auth_method)` 分发

#### Scenario: 旧客户端未传 auth_method
- **WHEN** 请求不包含 `auth_method`
- **THEN** 服务按默认策略推导 auth method 并保持兼容

### Requirement: OpenAI 鉴权 MUST 支持 2x2 组合（限定范围）
系统 MUST 为 `codex` 与 `opencode/provider=openai` 支持 2x2 鉴权矩阵。

#### Scenario: codex 2x2 可启动
- **WHEN** `engine=codex` 且 `transport in {oauth_proxy,cli_delegate}` 且 `auth_method in {browser-oauth,device-auth}`
- **THEN** 会话成功创建并进入非终态

#### Scenario: opencode/openai 2x2 可启动
- **WHEN** `engine=opencode, provider_id=openai` 且 `transport in {oauth_proxy,cli_delegate}` 且 `auth_method in {browser-oauth,device-auth}`
- **THEN** 会话成功创建并进入非终态

#### Scenario: 不支持组合返回 422
- **WHEN** 请求组合不在支持矩阵内
- **THEN** 返回 `422` 并包含组合非法提示

### Requirement: OpenAI browser OAuth MUST 支持 callback + input fallback
系统 MUST 允许浏览器回调成功闭环，并在回调不可达时提供 `/input` 兜底。

#### Scenario: callback 自动闭环
- **WHEN** callback 提供合法 `state + code`
- **THEN** 会话进入 `succeeded`

#### Scenario: 手工输入兜底
- **WHEN** 会话处于 `waiting_user`
- **AND** 客户端调用 `POST /v1/engines/auth/sessions/{id}/input`
- **THEN** `kind=text|code` 可用于提交 redirect URL 或授权码并完成闭环

### Requirement: OpenAI oauth_proxy + device-auth MUST 为零 CLI 协议路径
系统 MUST 在 `oauth_proxy + device-auth` 路径禁止 CLI/PTY 调用。

#### Scenario: device-auth 协议代理
- **WHEN** `transport=oauth_proxy, auth_method=device-auth`
- **THEN** 会话返回 `verification_url + user_code`
- **AND** 后端按协议轮询完成 token 交换
- **AND** 不调用 CLI/PTY/subprocess
