# interactive-run-lifecycle Specification

## Purpose
TBD - created by archiving change interactive-10-orchestrator-waiting-user-and-slot-release. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 支持可暂停的交互执行生命周期
The system MUST allow entering `waiting_user` based on the interactive done-marker gate, and MUST NOT require ask_user payload validity as a prerequisite.

#### Scenario: interactive 回合未完成进入等待态
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** 当前回合未检测到 `__SKILL_DONE__`
- **AND** 进程未进入中断失败
- **THEN** run 状态切换为 `waiting_user`
- **AND** 系统持久化 pending interaction（由后端生成基线）

#### Scenario: 非法 ask_user 不阻断等待态
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** assistant 输出中包含不合法 ask_user 结构
- **THEN** 系统仍可进入 `waiting_user`
- **AND** 不因 ask_user 结构错误直接标记 run 失败

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

### Requirement: auto 与 interactive MUST 采用不同完成门控
系统 MUST 对 `auto` 与 `interactive` 执行模式使用不同完成判定策略。

#### Scenario: auto 模式成功判定
- **WHEN** run 处于 `auto` 模式
- **AND** 进程执行成功且输出通过 schema 校验
- **THEN** run 进入 `succeeded`
- **AND** 不要求强制检测 `__SKILL_DONE__`

#### Scenario: interactive 模式成功判定
- **WHEN** run 处于 `interactive` 模式
- **AND** 检测到 `__SKILL_DONE__`
- **AND** 输出通过 schema 校验
- **THEN** run 进入 `succeeded`

#### Scenario: interactive 模式 marker 命中但输出校验失败
- **WHEN** run 处于 `interactive` 模式
- **AND** 检测到 `__SKILL_DONE__`
- **AND** 输出解析失败或 schema 校验失败
- **THEN** run MUST 进入 `failed`
- **AND** MUST NOT 进入 `waiting_user`

#### Scenario: interactive 模式软条件成功判定
- **WHEN** run 处于 `interactive` 模式
- **AND** 未检测到 `__SKILL_DONE__`
- **AND** 输出通过 schema 校验
- **THEN** run 进入 `succeeded`
- **AND** run 记录 warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

### Requirement: interactive 生命周期 MUST 支持最大回合限制
系统 MUST 支持 `runner.json.max_attempt`（可选）用于限制 interactive 最大交互回合数。

#### Scenario: 超过最大回合数触发失败
- **GIVEN** run 处于 `interactive` 模式且声明 `max_attempt`
- **WHEN** 当前 `attempt_number >= max_attempt`
- **AND** 当前回合既未检测到 `__SKILL_DONE__` 也未通过 output schema 软完成判定
- **THEN** run MUST 进入 `failed`
- **AND** 失败原因 MUST 包含 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`

#### Scenario: 未声明 max_attempt 允许无限回合
- **GIVEN** run 处于 `interactive` 模式且未声明 `max_attempt`
- **WHEN** 当前回合不满足完成证据
- **THEN** 系统按常规进入 `waiting_user`，不因回合数直接失败

