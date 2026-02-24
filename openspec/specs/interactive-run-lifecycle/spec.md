# interactive-run-lifecycle Specification

## Purpose
定义 interactive 生命周期在单一可恢复范式下的状态流转、并发槽位和完成门控语义。

## Requirements
### Requirement: 系统 MUST 支持可暂停交互生命周期
系统 MUST 在 interactive 回合无完成证据时进入 `waiting_user`，且不依赖 ask_user 结构完整性。

#### Scenario: 当前回合未完成进入等待态
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** 当前回合未检测到 `__SKILL_DONE__`
- **AND** 当前回合未命中 soft-complete
- **THEN** run 状态切换为 `waiting_user`
- **AND** 系统持久化 pending interaction

#### Scenario: ask_user 结构异常不阻断等待
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** assistant 输出包含不合法 ask_user 结构
- **THEN** 系统仍可进入 `waiting_user`

### Requirement: waiting_user 槽位语义 MUST 统一
系统 MUST 在进入 `waiting_user` 时释放执行槽位，并在恢复执行前重新申请槽位。

#### Scenario: 进入 waiting_user 释放槽位
- **GIVEN** run 已持有并发槽位
- **WHEN** run 进入 `waiting_user`
- **THEN** 系统释放该槽位

#### Scenario: 恢复执行前重新申请槽位
- **GIVEN** run 从 `waiting_user` 恢复执行
- **WHEN** 回到执行路径
- **THEN** 系统在进入 `running` 前重新申请槽位

### Requirement: strict 开关 MUST 控制超时后行为
系统 MUST 根据 `interactive_require_user_reply` 执行超时后的分流。

#### Scenario: strict=true 保持等待
- **GIVEN** `interactive_require_user_reply=true`
- **WHEN** run 进入 `waiting_user` 且等待超过 `session_timeout_sec`
- **THEN** run 保持 `waiting_user`
- **AND** 不因超时自动失败

#### Scenario: strict=false 自动决策继续执行
- **GIVEN** `interactive_require_user_reply=false`
- **WHEN** run 在 `waiting_user` 等待超过 `session_timeout_sec`
- **THEN** 系统生成自动决策回复
- **AND** run 回到 `queued` 并继续执行

### Requirement: auto 与 interactive MUST 使用统一状态机且策略不同
系统 MUST 在同一状态机下区分 `auto` 与 `interactive` 的完成策略。

#### Scenario: auto 模式成功判定
- **WHEN** run 处于 `auto` 模式
- **AND** 进程执行成功且输出通过 schema 校验
- **THEN** run 进入 `succeeded`

#### Scenario: interactive 模式强条件完成
- **WHEN** run 处于 `interactive` 模式
- **AND** 检测到 `__SKILL_DONE__`
- **AND** 输出通过 schema 校验
- **THEN** run 进入 `succeeded`

#### Scenario: interactive 模式软条件完成
- **WHEN** run 处于 `interactive` 模式
- **AND** 未检测到 `__SKILL_DONE__`
- **AND** 输出通过 schema 校验
- **THEN** run 进入 `succeeded`
- **AND** 记录 warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

### Requirement: interactive MUST 支持最大回合限制
系统 MUST 支持 `runner.json.max_attempt` 限制交互回合数。

#### Scenario: 超过最大回合触发失败
- **GIVEN** run 处于 `interactive` 模式且声明 `max_attempt`
- **WHEN** `attempt_number >= max_attempt` 且当前回合无完成证据
- **THEN** run 进入 `failed`
- **AND** 错误码包含 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
