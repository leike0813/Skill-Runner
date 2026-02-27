## ADDED Requirements

### Requirement: 鉴权会话日志 MUST 按 transport 分目录管理
系统 MUST 将鉴权会话日志按 `transport + session_id` 分目录组织，避免多 transport 混写。

#### Scenario: oauth_proxy 日志目录
- **WHEN** 创建 `oauth_proxy` 会话
- **THEN** 日志写入 `data/engine_auth_sessions/oauth_proxy/<session_id>/`
- **AND** 至少包含 `events.jsonl` 与 `http_trace.log`

#### Scenario: cli_delegate 日志目录
- **WHEN** 创建 `cli_delegate` 会话
- **THEN** 日志写入 `data/engine_auth_sessions/cli_delegate/<session_id>/`
- **AND** 至少包含 `events.jsonl`、`pty.log`、`stdin.log`

### Requirement: 系统 MUST 提供标准化鉴权事件流
系统 MUST 记录统一 `events.jsonl` 事件，覆盖状态迁移、输入、回调与终态。

#### Scenario: 状态迁移写事件
- **WHEN** 会话状态从一个节点迁移到另一个节点
- **THEN** 系统写入 `state_changed` 事件
- **AND** 事件包含 `from/to/transport/timestamp`

### Requirement: transport 状态机约束 MUST 可观测
系统 MUST 在快照与事件中体现 transport 专属状态机约束，便于自动化检测。

#### Scenario: oauth_proxy 禁止 waiting_orchestrator
- **WHEN** 会话 `transport=oauth_proxy`
- **THEN** 快照状态不允许为 `waiting_orchestrator`
- **AND** 若出现则记录 `driver_error` 并进入 `failed`

#### Scenario: cli_delegate 禁止 polling_result
- **WHEN** 会话 `transport=cli_delegate`
- **THEN** 快照状态不允许为 `polling_result`
- **AND** 若出现则记录 `driver_error` 并进入 `failed`
