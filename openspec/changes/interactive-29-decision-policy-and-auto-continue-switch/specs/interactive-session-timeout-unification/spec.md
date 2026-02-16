## ADDED Requirements

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
