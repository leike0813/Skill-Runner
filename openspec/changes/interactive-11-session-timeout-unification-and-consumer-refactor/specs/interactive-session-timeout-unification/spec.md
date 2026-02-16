## ADDED Requirements

### Requirement: 系统 MUST 只使用统一会话超时配置键
系统 MUST 将会话级 hard timeout 统一为 `session_timeout_sec`，默认值为 `1200` 秒。

#### Scenario: 未提供超时配置
- **WHEN** run 未显式配置会话超时
- **THEN** 系统使用默认 `session_timeout_sec=1200`

#### Scenario: 提供统一超时配置
- **WHEN** run 或系统配置显式提供 `session_timeout_sec`
- **THEN** 系统使用该值作为会话 hard timeout

### Requirement: 系统 MUST 对历史超时命名提供受控兼容
系统 MUST 在迁移期兼容历史命名，并定义明确优先级。

#### Scenario: 仅存在历史键
- **GIVEN** 未提供 `session_timeout_sec`
- **WHEN** 配置中存在历史键（如 `interactive_wait_timeout_sec`）
- **THEN** 系统将其映射为 `session_timeout_sec`
- **AND** 记录 deprecation 提示

#### Scenario: 新旧键同时存在
- **WHEN** `session_timeout_sec` 与历史键同时存在
- **THEN** 系统以 `session_timeout_sec` 为准
- **AND** 历史键被忽略并记录提示

### Requirement: 所有 hard timeout 消费位点 MUST 使用归一化会话超时
系统 MUST 确保 hard timeout 的计算与执行使用统一归一化值。

#### Scenario: 计算等待截止时间
- **WHEN** `sticky_process` run 进入 `waiting_user`
- **THEN** 系统基于归一化 `session_timeout_sec` 写入 `wait_deadline_at`

#### Scenario: 执行超时终止
- **WHEN** 当前时间超过 `wait_deadline_at`
- **THEN** 系统终止对应进程
- **AND** run 进入 `failed`
- **AND** `error.code=INTERACTION_WAIT_TIMEOUT`
