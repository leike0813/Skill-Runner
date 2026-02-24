## MODIFIED Requirements

### Requirement: 系统 MUST 按 interactive_profile 管理 waiting_user 槽位
系统 MUST 使用统一槽位语义：进入 `waiting_user` 释放槽位，恢复前重新申请。

#### Scenario: waiting_user 释放槽位
- **WHEN** run 进入 `waiting_user`
- **THEN** 系统释放当前执行槽位

#### Scenario: resume 前重新申请槽位
- **WHEN** run 从 `waiting_user` 恢复下一回合
- **THEN** 系统在 `running` 前重新申请槽位

### Requirement: waiting_user 行为 MUST 受 strict 开关控制
系统 MUST 收敛 strict 分流行为。

#### Scenario: strict=true 不超时失败
- **GIVEN** `interactive_require_user_reply=true`
- **WHEN** 等待超过 `session_timeout_sec`
- **THEN** run 保持 `waiting_user`

#### Scenario: strict=false 自动决策推进
- **GIVEN** `interactive_require_user_reply=false`
- **WHEN** 等待超过 `session_timeout_sec`
- **THEN** 系统自动决策并将 run 回到 `queued` 继续执行
