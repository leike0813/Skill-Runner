# interactive-run-lifecycle Specification

## Purpose
定义 interactive 生命周期在单一可恢复范式下的状态流转、并发槽位和完成门控语义。
## Requirements
### Requirement: 系统 MUST 支持可暂停交互生命周期
系统 MUST 在 interactive 回合无完成证据时进入 `waiting_user`，且不依赖 ask_user 结构完整性；但高置信度 auth detection 必须优先于 generic `waiting_user` 推断。

#### Scenario: 高置信度鉴权证据阻止 waiting_user
- **GIVEN** 输出包含高置信度 auth-required 证据
- **WHEN** run_job 归一化结果
- **THEN** 系统不得进入 `waiting_user`
- **AND** generic pending interaction 推断必须被跳过

#### Scenario: medium 问题样本保持保守
- **GIVEN** 输出只命中 medium 级问题样本
- **WHEN** run_job 归一化结果
- **THEN** 系统可以继续现有等待态逻辑
- **AND** 必须保留 auth detection 审计字段

### Requirement: waiting_user 槽位语义 MUST 统一
系统 MUST 将 `waiting_auth` 视为与 `waiting_user` 同级的暂停态：进入等待态时释放执行槽位，恢复执行前重新申请槽位。

#### Scenario: 进入 waiting_auth 释放槽位
- **GIVEN** run 已持有并发槽位
- **WHEN** run 进入 `waiting_auth`
- **THEN** 系统释放该槽位

#### Scenario: auth 恢复执行前重新申请槽位
- **GIVEN** run 从 `waiting_auth` 恢复执行
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

### Requirement: waiting states MUST use a single-consumer resume contract
The system MUST use one durable resume ownership path when leaving `waiting_auth` or `waiting_user`.

#### Scenario: duplicate resume contenders race on the same waiting run
- **GIVEN** callback completion, reconcile, and restart recovery observe the same resumable waiting run
- **WHEN** they attempt to resume the run concurrently
- **THEN** only one path wins the durable resume ticket
- **AND** the non-winners MUST NOT advance the run state a second time

### Requirement: waiting state applicability MUST follow conversation capability
The system MUST gate `waiting_auth` and real `waiting_user` by `client_metadata.conversation_mode`, not by `execution_mode` alone.

#### Scenario: session-capable auto run hits auth
- **GIVEN** a run uses `execution_mode=auto`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** high-confidence auth is detected
- **THEN** the run MAY enter `waiting_auth`

#### Scenario: non-session run hits auth
- **GIVEN** a run uses `client_metadata.conversation_mode=non_session`
- **WHEN** high-confidence auth is detected
- **THEN** the run MUST NOT enter `waiting_auth`
- **AND** the backend MUST preserve fail-fast auth behavior

#### Scenario: non-session interactive execution needs user reply
- **GIVEN** a run resolves to `execution_mode=interactive`
- **AND** `client_metadata.conversation_mode=non_session`
- **WHEN** the skill would otherwise require user reply
- **THEN** the backend MUST normalize execution to zero-timeout auto-reply
- **AND** the run MUST NOT expose a real `waiting_user` state

### Requirement: resumed execution MUST materialize exactly one target attempt
The system MUST determine and materialize exactly one target attempt before `turn.started`.

#### Scenario: waiting-state resume is accepted
- **GIVEN** a waiting run has an accepted resume ticket
- **WHEN** the resumed execution is scheduled
- **THEN** the system MUST determine `target_attempt` before `turn.started`
- **AND** the same resume flow MUST NOT emit more than one `lifecycle.run.started` for that attempt

### Requirement: waiting-state pending data MUST be attempt-scoped
The system MUST keep current pending data and append-only history in separate attempt-aware layers.

#### Scenario: a run transitions from waiting to a new attempt
- **GIVEN** a run leaves `waiting_user` or `waiting_auth`
- **WHEN** the system persists the current pending owner and historical interaction/auth rows
- **THEN** current pending data MUST represent only the live waiting owner
- **AND** history entries MUST retain the source attempt that produced them

### Requirement: restart recovery MUST preserve resume ownership semantics
Restart recovery MUST reuse the same canonical resume ownership contract as live callback/reconcile paths.

#### Scenario: service restarts while a run is resumable
- **GIVEN** the service restarts while a run has a resumable waiting state
- **WHEN** recovery reconciles the run
- **THEN** recovery MUST reuse the same durable resume ownership contract
- **AND** recovery MUST NOT create a second competing resume path

### Requirement: `waiting_auth` MUST support internal phases
The system MUST represent `waiting_auth` with explicit internal phases: `method_selection` and `challenge_active`.

#### Scenario: run enters waiting_auth
- **GIVEN** a run enters `waiting_auth`
- **WHEN** pending auth payload and auth session status are read
- **THEN** phase MUST be explicitly readable
- **AND** phase MUST distinguish `method_selection` and `challenge_active`

### Requirement: `waiting_auth` timeout MUST be auth-session scoped
Auth timeout MUST be counted only for active auth sessions.

#### Scenario: phase changes from selection to challenge
- **GIVEN** a run is in `waiting_auth`
- **WHEN** phase is `method_selection`
- **THEN** auth timeout MUST NOT be counted
- **WHEN** phase is `challenge_active`
- **THEN** auth timeout MUST be enforced per auth session

### Requirement: busy auth session MUST keep run in `waiting_auth`
When active auth session blocks new session creation, run state MUST remain `waiting_auth`.

#### Scenario: auth session creation is blocked by active session
- **GIVEN** a run is waiting for auth
- **WHEN** a new auth session cannot be created due to an existing active session
- **THEN** run state MUST remain `waiting_auth`
- **AND** the client MUST receive an explicit error

