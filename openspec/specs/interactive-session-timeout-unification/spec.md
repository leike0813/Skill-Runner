# interactive-session-timeout-unification Specification

## Purpose
定义 interactive 会话超时的统一配置、消费位点与 strict 分流行为。

## Requirements
### Requirement: 系统 MUST 使用统一会话超时键
系统 MUST 将会话级超时统一为 `session_timeout_sec`，默认值 `1200` 秒。

#### Scenario: 未提供会话超时
- **WHEN** run 未显式配置 `session_timeout_sec`
- **THEN** 系统使用默认值 `1200`

#### Scenario: 显式提供会话超时
- **WHEN** run 提供 `session_timeout_sec`
- **THEN** 系统使用该值作为会话超时

### Requirement: 系统 MUST 提供受控历史键兼容
系统 MUST 在迁移期兼容历史超时命名，并定义优先级。

#### Scenario: 仅存在历史键
- **GIVEN** 未提供 `session_timeout_sec`
- **WHEN** 配置中存在历史键（如 `interactive_wait_timeout_sec`）
- **THEN** 系统将其映射为 `session_timeout_sec`

#### Scenario: 新旧键同时存在
- **WHEN** `session_timeout_sec` 与历史键同时存在
- **THEN** 系统以 `session_timeout_sec` 为准

### Requirement: strict=false MUST 以会话超时触发自动决策
系统 MUST 使用统一 `session_timeout_sec` 作为 strict=false 的自动决策触发计时。

#### Scenario: strict=false 超时自动推进
- **GIVEN** run 进入 `waiting_user`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 等待达到 `session_timeout_sec`
- **THEN** 系统触发自动决策路径并继续执行

### Requirement: strict=true MUST NOT 因会话超时自动失败
系统 MUST 在 strict=true 场景保持等待语义。

#### Scenario: strict=true 超时保持等待
- **GIVEN** run 进入 `waiting_user`
- **AND** `interactive_require_user_reply=true`
- **WHEN** 等待达到 `session_timeout_sec`
- **THEN** run 保持 `waiting_user`
- **AND** 不自动转为 `failed`
