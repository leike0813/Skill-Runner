## ADDED Requirements

### Requirement: Waiting interaction persistence MUST require a persisted session handle
交互 run 在进入 `waiting_user` 持久化时 MUST 已存在可恢复会话句柄，系统 MUST NOT 再从 raw 输出临时提取。

#### Scenario: waiting_user with eventized handle available
- **GIVEN** 引擎在运行期已发布并持久化 `lifecycle.run_handle`
- **WHEN** orchestrator 持久化 `waiting_user` 交互数据
- **THEN** 系统 MUST 直接复用已持久化 handle
- **AND** MUST NOT 调用 `extract_session_handle(raw_output, ...)`

#### Scenario: waiting_user without persisted handle
- **GIVEN** run 进入 `waiting_user` 分支前未持久化 session handle
- **WHEN** orchestrator 执行 waiting interaction 持久化
- **THEN** 系统 MUST 返回 `SESSION_RESUME_FAILED`
- **AND** run MUST NOT 以 waiting_user 继续挂起
