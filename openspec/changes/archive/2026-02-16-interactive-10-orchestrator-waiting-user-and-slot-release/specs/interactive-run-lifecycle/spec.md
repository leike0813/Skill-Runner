## ADDED Requirements

### Requirement: 系统 MUST 支持可暂停的交互执行生命周期
系统 MUST 允许 run 在执行中进入 `waiting_user`，并在收到用户回复后继续执行。

#### Scenario: 执行中请求用户决策
- **WHEN** 执行回合返回 `ask_user`
- **THEN** run 状态切换为 `waiting_user`
- **AND** 系统持久化当前 pending interaction

#### Scenario: 用户提交回复后继续执行
- **GIVEN** run 处于 `waiting_user`
- **WHEN** 系统接收合法回复
- **THEN** run 按 `interactive_profile.kind` 进入对应恢复路径并继续下一回合执行

### Requirement: 系统 MUST 按 interactive_profile 管理 waiting_user 槽位
系统 MUST 根据 `interactive_profile.kind` 执行分支化槽位策略。

#### Scenario: resumable waiting_user 释放槽位
- **GIVEN** run 已持有并发槽位并进入 `waiting_user`
- **AND** `interactive_profile.kind=resumable`
- **THEN** 系统释放该槽位
- **AND** 其他队列任务可获得执行机会

#### Scenario: resumable 恢复执行前重新申请槽位
- **GIVEN** `interactive_profile.kind=resumable`
- **WHEN** run 从 `waiting_user` 恢复执行
- **THEN** 系统在进入 `running` 前重新申请并发槽位

#### Scenario: sticky_process waiting_user 保持槽位
- **GIVEN** run 已持有并发槽位并进入 `waiting_user`
- **AND** `interactive_profile.kind=sticky_process`
- **THEN** 系统保持该槽位不释放
- **AND** run 继续绑定原执行进程

### Requirement: sticky_process MUST 具备等待超时回收
系统 MUST 在 `sticky_process` 的等待阶段按统一会话超时 `session_timeout_sec`（默认 1200 秒）设置截止时间，并在超时后终止进程。

#### Scenario: sticky_process 超时失败
- **GIVEN** run 处于 `waiting_user` 且 `interactive_profile.kind=sticky_process`
- **WHEN** 等待时间超过 `wait_deadline_at` 且无 reply
- **THEN** 系统终止驻留进程
- **AND** run 进入 `failed`
- **AND** `error.code=INTERACTION_WAIT_TIMEOUT`

### Requirement: 系统 MUST 记录交互历史
系统 MUST 持久化每次问答回合，供审计与重放排障。

#### Scenario: 记录 ask/reply 历史
- **WHEN** run 完成一次 ask_user 与 reply
- **THEN** 系统保存包含 interaction_id、prompt、response、时间戳的历史记录
