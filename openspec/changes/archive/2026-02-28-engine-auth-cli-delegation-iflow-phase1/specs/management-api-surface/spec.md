## ADDED Requirements

### Requirement: 系统 MUST 支持 iFlow 鉴权会话创建
系统 MUST 在现有 `/v1/engines/auth/sessions` 下支持 iFlow 鉴权会话创建参数组合。

#### Scenario: 创建 iFlow 鉴权会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **AND** 请求体为 `{"engine":"iflow","method":"iflow-cli-oauth"}`
- **THEN** 系统创建会话并返回快照

### Requirement: 系统 MUST 允许 iFlow 会话使用 submit 提交授权码
系统 MUST 允许 iFlow auth session 通过既有 submit 接口提交 authorization code。

#### Scenario: iFlow submit 成功
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/submit`
- **AND** 会话属于 iFlow CLI OAuth 流
- **THEN** 系统写入 code 并返回最新会话快照

#### Scenario: submit 会话不存在
- **WHEN** 客户端提交不存在的 `session_id`
- **THEN** 返回 `404`

#### Scenario: submit 不支持的会话类型
- **WHEN** 会话既不是 Gemini 也不是 iFlow 委托鉴权会话
- **THEN** 返回 `422`
