## MODIFIED Requirements

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

## ADDED Requirements

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
