## ADDED Requirements

### Requirement: waiting_auth MUST support import as a conversation auth method
当会话鉴权策略声明 `import` 时，交互式 run 在 `waiting_auth` 阶段 MUST 允许通过文件导入完成鉴权。

#### Scenario: auth import is accepted and resumes run
- **GIVEN** run 当前状态为 `waiting_auth`
- **AND** pending auth method selection 包含 `import`
- **WHEN** client 调用 `POST /v1/jobs/{request_id}/interaction/auth/import` 并上传通过校验的文件
- **THEN** backend MUST 清理 pending auth 状态并发出 `auth.session.completed`
- **AND** run MUST 进入 queued/running 恢复路径

#### Scenario: auth import is rejected when method is unavailable
- **GIVEN** run 不在 `waiting_auth` 或当前可用方法不包含 `import`
- **WHEN** client 调用导入接口
- **THEN** backend MUST 返回可诊断错误（409/422）
- **AND** MUST NOT 改写当前 pending 状态
