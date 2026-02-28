## ADDED Requirements

### Requirement: 系统 MUST 提供引擎鉴权会话式 API
系统 MUST 在 `/v1/engines` 下提供 start/status/cancel 三个鉴权会话接口，首期支持 `codex` 的 `device-auth`。

#### Scenario: 创建鉴权会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions`
- **AND** 请求体为 `{"engine":"codex","method":"device-auth"}`
- **THEN** 系统创建会话并返回会话快照

#### Scenario: 查询鉴权会话
- **WHEN** 客户端调用 `GET /v1/engines/auth/sessions/{session_id}`
- **THEN** 系统返回对应会话快照
- **AND** 不存在的会话返回 `404`

#### Scenario: 取消鉴权会话
- **WHEN** 客户端调用 `POST /v1/engines/auth/sessions/{session_id}/cancel`
- **THEN** 系统停止该会话并返回取消结果

### Requirement: 鉴权会话 API MUST 提供稳定错误语义
系统 MUST 为鉴权会话接口提供稳定错误码，便于前端统一处理。

#### Scenario: 未认证访问
- **WHEN** UI Basic Auth 开启且客户端未认证
- **THEN** 接口返回 `401`

#### Scenario: 不支持引擎或方法
- **WHEN** 请求参数不是首期支持范围（非 `codex` 或非 `device-auth`）
- **THEN** 接口返回 `422`

#### Scenario: 互斥冲突
- **WHEN** 当前存在活跃 TUI 会话或活跃鉴权会话
- **THEN** start 接口返回 `409`

#### Scenario: 进程异常
- **WHEN** 启动或轮询过程出现进程级异常
- **THEN** 接口返回 `500` 或在会话快照中体现 `failed` + `error`
