## ADDED Requirements

### Requirement: Auth observability behavior MUST remain stable after hard cutover
phase2 删除兼容层后，鉴权会话状态与审计语义 MUST 保持兼容。

#### Scenario: Auth observability regression check
- **WHEN** 执行现有鉴权流程并读取会话快照
- **THEN** 状态推进、终态与关键审计字段语义不变

### Requirement: Delegated auth trust injection MUST remain active after decoupling
CLI delegated auth start 前 MUST 继续执行 run folder trust 注入。

#### Scenario: Delegated auth trust strategy invocation
- **WHEN** 启动 `cli_delegate` 鉴权会话
- **THEN** orchestration trust manager 会在会话目录创建前后调用对应引擎策略
- **AND** 会话终态时执行 trust 清理

### Requirement: Engine auth manager MUST behave as orchestration façade
`engine_auth_flow_manager` MUST 将 flow/listener/handler/matrix 装配外移，避免 manager 继续承载装配职责。

#### Scenario: Bootstrap ownership
- **WHEN** 初始化 auth orchestration
- **THEN** flow/listener/handler/matrix 由 bootstrap 模块装配
- **AND** manager 仅保留 façade 与生命周期调度职责
