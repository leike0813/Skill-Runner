## ADDED Requirements

### Requirement: 系统 MUST 提供鉴权会话授权码提交接口
系统 MUST 在现有 `/v1/engines/auth/sessions` 体系下提供 submit 子动作，支持回传 Gemini authorization code。

#### Scenario: 提交授权码
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/submit`
- **AND** 请求体包含 `code`
- **THEN** 系统将 code 写入对应会话并返回最新会话快照

#### Scenario: 会话不存在
- **WHEN** 客户端提交不存在的 `session_id`
- **THEN** 返回 `404`

#### Scenario: 不支持 submit 的引擎/方法
- **WHEN** 会话不属于 Gemini screen-reader 流
- **THEN** 返回 `422`

### Requirement: Gemini 委托编排鉴权 API MUST 提供稳定状态语义
系统 MUST 在会话快照中暴露 Gemini 状态机状态，供前端轮询与错误处理。

#### Scenario: Gemini 状态可见
- **WHEN** 客户端查询 Gemini 鉴权会话
- **THEN** `status` 属于 `starting|waiting_user|waiting_user_code|code_submitted_waiting_result|succeeded|failed|canceled|expired`

