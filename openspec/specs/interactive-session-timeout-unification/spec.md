# interactive-session-timeout-unification Specification

## Purpose
TBD - created by archiving change interactive-11-session-timeout-unification-and-consumer-refactor. Update Purpose after archive.
## Requirements
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

### Requirement: 会话超时 MUST 同时用于自动决策触发
系统 MUST 使用统一 `session_timeout_sec` 作为 strict=false 场景下的自动决策触发计时。

#### Scenario: strict=false 的自动决策计时
- **GIVEN** run 进入 `waiting_user`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 计时达到 `session_timeout_sec`
- **THEN** 系统触发自动决策路径（而非 strict=true 的失败路径）

### Requirement: strict=true 与 strict=false 在超时后 MUST 分流
系统 MUST 在超时时按 strict 开关执行不同后果。

#### Scenario: strict=true 超时分流
- **WHEN** `interactive_require_user_reply=true` 且触发等待超时
- **THEN** `sticky_process` 路径失败（`INTERACTION_WAIT_TIMEOUT`）

#### Scenario: strict=false 超时分流
- **WHEN** `interactive_require_user_reply=false` 且触发等待超时
- **THEN** 系统执行自动决策并继续回合
- **AND** 不因该次超时直接失败

