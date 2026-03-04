## MODIFIED Requirements

### Requirement: 写入路径 MUST 严格校验
系统 MUST 在协议对象落盘/输出前执行 schema 校验，并确保 auth orchestrator event 的 canonical 写入路径被 schema 完整覆盖。

#### Scenario: 不合法事件写入
- **WHEN** 协议对象不满足 schema
- **THEN** 写入被拒绝并返回 `PROTOCOL_SCHEMA_VIOLATION`

#### Scenario: auth orchestrator event canonical payload 通过校验
- **WHEN** orchestration 写入 `auth.session.created`、`auth.method.selected`、`auth.session.busy`、`auth.input.accepted`、`auth.session.completed`、`auth.session.failed` 或 `auth.session.timed_out`
- **THEN** schema MUST 接受这些 canonical payload
- **AND** 系统 MUST NOT 因 schema 漂移把合法 auth submit/complete/fail 路径升级成 `500`

#### Scenario: auth.input.accepted 接受 canonical timestamp 字段
- **WHEN** orchestration 为 callback/code 提交写入 `auth.input.accepted`
- **THEN** 其 `data` MAY 包含 canonical `accepted_at`
- **AND** schema MUST 明确允许该字段
- **AND** 仍 MUST 拒绝未声明的额外字段
