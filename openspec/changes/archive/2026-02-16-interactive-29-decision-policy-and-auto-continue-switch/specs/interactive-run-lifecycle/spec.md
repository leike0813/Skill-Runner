## ADDED Requirements

### Requirement: waiting_user 行为 MUST 受 strict 开关控制
系统 MUST 根据 `interactive_require_user_reply` 与 `interactive_profile.kind` 执行分支化 waiting_user 策略。

#### Scenario: resumable + strict=true
- **GIVEN** `interactive_profile.kind=resumable`
- **AND** `interactive_require_user_reply=true`
- **WHEN** run 进入 `waiting_user`
- **THEN** 系统不自动推进下一回合
- **AND** run 保持未完成状态直到用户回复或取消

#### Scenario: sticky_process + strict=true
- **GIVEN** `interactive_profile.kind=sticky_process`
- **AND** `interactive_require_user_reply=true`
- **WHEN** 等待超过会话超时
- **THEN** 系统终止进程并标记失败
- **AND** `error.code=INTERACTION_WAIT_TIMEOUT`

#### Scenario: resumable + strict=false
- **GIVEN** `interactive_profile.kind=resumable`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 等待超过会话超时
- **THEN** 系统生成自动决策回复并发起 resume 回合
- **AND** run 继续执行而非直接失败

#### Scenario: sticky_process + strict=false
- **GIVEN** `interactive_profile.kind=sticky_process`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 等待超过会话超时
- **THEN** 系统向驻留进程注入自动决策指令
- **AND** run 继续执行而非直接失败
