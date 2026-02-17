## ADDED Requirements

### Requirement: 系统 MUST 暴露 waiting_user 的可观测状态
系统 MUST 在状态接口中明确体现 run 是否处于等待用户输入阶段。

#### Scenario: 查询 waiting_user 状态
- **GIVEN** run 当前在等待用户输入
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}`
- **THEN** 响应 `status=waiting_user`
- **AND** 包含当前待决交互标识（如 `pending_interaction_id`）

### Requirement: 日志轮询建议 MUST 区分 waiting_user 与 running
系统 MUST 在等待用户阶段关闭“继续轮询日志”的建议标志。

#### Scenario: waiting_user 的日志 tail
- **WHEN** 客户端调用 logs tail 接口且 run 状态为 `waiting_user`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `false`

#### Scenario: running 的日志 tail
- **WHEN** run 状态为 `running`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `true`

### Requirement: 文档 MUST 定义交互模式 API 时序
系统文档 MUST 提供 interactive 模式的 API 时序和错误处理建议。

#### Scenario: 文档覆盖 pending/reply 流程
- **WHEN** 开发者查阅 API 文档
- **THEN** 可获得 create -> pending -> reply -> resume -> terminal 的完整流程
- **AND** 文档明确说明本阶段仅支持 API 交互，不提供 UI 交互入口
