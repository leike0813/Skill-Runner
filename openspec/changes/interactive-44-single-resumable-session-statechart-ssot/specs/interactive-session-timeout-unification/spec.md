## MODIFIED Requirements

### Requirement: 所有 hard timeout 消费位点 MUST 使用归一化会话超时
系统 MUST 仅用 `session_timeout_sec` 驱动等待超时策略。

#### Scenario: strict=false 超时触发自动决策
- **GIVEN** run 处于 `waiting_user`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 超过 `session_timeout_sec`
- **THEN** 系统触发自动决策并继续执行

### Requirement: strict=true 与 strict=false 在超时后 MUST 分流
系统 MUST 明确 strict=true 不超时失败。

#### Scenario: strict=true 超时仍等待
- **GIVEN** `interactive_require_user_reply=true`
- **WHEN** 超过 `session_timeout_sec`
- **THEN** run 保持 `waiting_user`
