## ADDED Requirements

### Requirement: 引擎鉴权会话 MUST 统一通过 input 接口接收用户输入
系统 MUST 提供统一输入接口以承载授权码、API key 及其他文本输入。

#### Scenario: 提交统一输入
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/input`
- **AND** 请求体包含 `kind` 与 `value`
- **THEN** 系统将输入分发到对应会话 driver 并返回最新会话快照

#### Scenario: 输入类型非法
- **WHEN** 请求体 `kind` 不在 `code|api_key|text` 集合
- **THEN** 返回 `422`

#### Scenario: 会话不存在
- **WHEN** `session_id` 不存在
- **THEN** 返回 `404`

### Requirement: OpenCode auth start MUST 支持 provider_id 参数
系统 MUST 允许 OpenCode 鉴权会话启动时声明 provider。

#### Scenario: 启动 OpenCode provider 会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **AND** 请求体为 `{"engine":"opencode","method":"opencode-provider-auth","provider_id":"openai"}`
- **THEN** 系统创建会话并返回快照

## REMOVED Requirements

### Requirement: 系统 MUST 移除 submit 接口
系统 MUST 删除旧的 auth `submit` 接口，避免与统一 input 语义并存。

#### Scenario: submit 端点不再可用
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/submit`
- **THEN** 返回 `404` 或 `405`
