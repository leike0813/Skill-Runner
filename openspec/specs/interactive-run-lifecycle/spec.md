# interactive-run-lifecycle Specification

## Purpose
定义 interactive 生命周期在单一可恢复范式下的状态流转、并发槽位和完成门控语义。
## Requirements
### Requirement: interactive 终态门禁 MUST 先判 ask_user 再判 soft completion
interactive 模式 MUST 先消费 done marker 与 ask-user 证据，再允许 structured output 走 soft completion。

#### Scenario: ask_user 证据阻止 soft completion
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 命中 `<ASK_USER_YAML>` 或显式 ask_user 证据
- **THEN** run MUST 进入 `waiting_user`
- **AND** 不得因为 output schema 通过而直接进入 `succeeded`

#### Scenario: extracted JSON but schema invalid keeps waiting
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 成功提取标准化 JSON
- **AND** output schema 校验失败
- **THEN** run MUST 进入 `waiting_user`
- **AND** 不得直接进入 `failed`

#### Scenario: no ask_user and no JSON also keeps waiting
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 未提取到标准化 JSON
- **THEN** run MUST 进入 `waiting_user`

### Requirement: interactive soft completion MUST require valid structured output
interactive 模式下的 soft completion MUST 仅在标准化 JSON、schema 校验和 artifact 修复同时成立时触发。

#### Scenario: soft completion requires schema and artifact validation
- **WHEN** 当前 attempt 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 提取到标准化 JSON
- **AND** output schema 校验通过
- **AND** best-effort artifact 路径修复后仍成立
- **THEN** run MAY 进入 `succeeded`

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
- **AND** 未命中 ask_user 证据
- **AND** 成功提取标准化 JSON
- **AND** 输出通过 schema 校验
- **THEN** run 进入 `succeeded`
- **AND** 记录 warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: ask_user 证据阻止 soft completion
- **WHEN** run 处于 `interactive` 模式
- **AND** 未检测到 `__SKILL_DONE__`
- **AND** 当前回合命中 `<ASK_USER_YAML>` 或其他 ask_user 证据
- **THEN** run 进入 `waiting_user`
- **AND** 不得因为 output schema 通过而直接进入 `succeeded`

#### Scenario: 提取到 JSON 但 schema 无效时保持等待
- **WHEN** run 处于 `interactive` 模式
- **AND** 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 成功提取标准化 JSON
- **AND** output schema 校验失败
- **THEN** run 进入 `waiting_user`
- **AND** 不得直接进入 `failed`

#### Scenario: 无 ask_user 且无 JSON 时保持等待
- **WHEN** run 处于 `interactive` 模式
- **AND** 未检测到 `__SKILL_DONE__`
- **AND** 未命中 ask_user 证据
- **AND** 未提取到标准化 JSON
- **THEN** run 进入 `waiting_user`

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

### Requirement: interactive 终态门禁 MUST 先判显式输出分支再决定生命周期
The target lifecycle contract MUST distinguish final vs pending JSON branches before any fallback logic.

#### Scenario: pending branch enters waiting_user
- **WHEN** the current turn emits a valid pending JSON branch
- **AND** `__SKILL_DONE__ = false`
- **AND** `message` and `ui_hints` are valid
- **THEN** the run MUST enter `waiting_user`

#### Scenario: final branch enters completion path
- **WHEN** the current turn emits a valid final JSON branch
- **AND** `__SKILL_DONE__ = true`
- **AND** business fields satisfy the output schema
- **THEN** the run MUST enter the completion path

#### Scenario: legacy soft completion is rollout-only
- **WHEN** historical notes mention completion without explicit done marker
- **THEN** they MUST be described as legacy rollout context only
- **AND** they MUST NOT define the target lifecycle contract

### Requirement: auto 与 interactive MUST 使用显式 done-marker 最终对象
The target JSON-only contract MUST require explicit final objects in both modes even though implementation rollout may occur later.

#### Scenario: auto final object is explicit
- **WHEN** run 处于 `auto` 模式
- **AND** the task is complete
- **THEN** the target final payload MUST include `__SKILL_DONE__ = true`

#### Scenario: interactive final object is explicit
- **WHEN** run 处于 `interactive` 模式
- **AND** the task is complete
- **THEN** the target final payload MUST include `__SKILL_DONE__ = true`

### Requirement: interactive waiting semantics MUST align to pending JSON branch
The future canonical source for `waiting_user` MUST be the compliant pending JSON branch rather than `<ASK_USER_YAML>` or other free-form wrapper semantics.

#### Scenario: legacy ask-user evidence is deprecated
- **WHEN** a turn uses `<ASK_USER_YAML>` instead of the pending JSON branch
- **THEN** that output MUST be classified as legacy deprecated semantics
- **AND** it MUST NOT remain the normative contract for compliant implementations

### Requirement: repair exhaustion MUST fall back without deciding waiting or failure directly
Repair retries MUST belong to the same attempt and MUST only return control to the existing lifecycle fallback when exhausted.

#### Scenario: repair stays attempt-local
- **WHEN** a turn enters repair retries
- **THEN** retries MUST remain inside the same attempt
- **AND** they MUST NOT increment `attempt_number`

#### Scenario: repair exhaustion returns control
- **WHEN** repair retries are exhausted
- **THEN** repair MUST stop
- **AND** control MUST return to the existing lifecycle normalization path
- **AND** repair exhaustion itself MUST NOT directly decide `waiting_user` or `failed`

### Requirement: Interactive Attempts Target the Union Contract

Interactive attempts MUST converge against the interactive union schema for both non-final
and final turns.

#### Scenario: Pending branch becomes the formal waiting source
- **WHEN** an interactive attempt converges to the pending branch of the union schema
- **THEN** runtime MUST project it into the canonical `PendingInteraction` shape
- **AND** the run MUST transition into `waiting_user`

#### Scenario: Legacy ask-user markup is not the formal waiting source
- **WHEN** interactive output contains legacy `<ASK_USER_YAML>` or similar deprecated markup
- **THEN** runtime MUST treat that output as an invalid legacy sample for convergence purposes
- **AND** it MUST NOT directly establish `waiting_user` from that markup alone

### Requirement: interactive lifecycle MUST distinguish attempt lifecycle from internal repair rounds
The target interactive lifecycle MUST treat repair rounds as attempt-internal convergence, not as lifecycle-level retries.

#### Scenario: repair rounds do not mutate attempt ownership
- **WHEN** an interactive turn enters output convergence
- **THEN** any repair rounds MUST remain inside the active attempt
- **AND** `attempt_number` ownership MUST remain unchanged until the lifecycle leaves that attempt

### Requirement: legacy waiting and completion semantics MUST be modeled as fallback stages
The current interactive waiting/completion heuristics MUST be documented as legacy fallbacks inside the unified convergence pipeline.

#### Scenario: ask-user evidence remains a legacy waiting fallback
- **WHEN** current runtime behavior derives `waiting_user` from `<ASK_USER_YAML>` or equivalent ask-user evidence
- **THEN** the spec MUST describe that path as `legacy / current implementation only`
- **AND** it MUST NOT be described as the target repair-owned waiting source

#### Scenario: soft completion remains a legacy completion fallback
- **WHEN** current runtime behavior completes an interactive turn without an explicit done marker
- **THEN** the spec MUST describe that path as `legacy / current implementation only`
- **AND** it MUST NOT be described as the target convergence contract

### Requirement: Interactive Waiting Uses Pending JSON As The Primary Source

Interactive runs MUST treat a valid pending JSON branch as the primary source of
`waiting_user`.

#### Scenario: Valid pending JSON projects directly into waiting_user
- **WHEN** an interactive attempt resolves the pending branch of the union schema
- **THEN** runtime MUST project that branch into canonical `PendingInteraction`
- **AND** the run MUST enter `waiting_user` without legacy enrichment

### Requirement: Legacy Waiting Fallback Is Generic

Legacy fallback MAY still produce `waiting_user`, but it MUST no longer derive
rich pending fields from deprecated output forms.

#### Scenario: Legacy fallback uses the default pending payload
- **WHEN** an interactive attempt does not converge to a valid pending/final
  branch and lifecycle still falls back to waiting
- **THEN** runtime MUST synthesize a default pending payload
- **AND** it MUST NOT recover prompt, kind, options, or hints from YAML wrappers,
  runtime-stream text, or direct interaction-like payloads

### Requirement: Interactive Lifecycle Uses Explicit Branch Priority First

Interactive lifecycle normalization MUST treat explicit final and pending
branches as the primary contract before any compatibility fallback.

#### Scenario: final branch outranks all compatibility paths
- **WHEN** an interactive attempt resolves a valid final branch
- **THEN** runtime MUST evaluate that branch before pending, soft completion, or
  waiting fallback

#### Scenario: pending branch outranks soft completion and waiting fallback
- **WHEN** an interactive attempt resolves a valid pending branch
- **THEN** runtime MUST enter `waiting_user`
- **AND** it MUST NOT continue into soft completion or generic waiting fallback

### Requirement: Compatibility Paths Remain Secondary

Phase 5 MUST keep compatibility completion and waiting paths, but only after the
explicit branches fail to resolve.

#### Scenario: soft completion remains available after branch miss
- **WHEN** an interactive attempt does not resolve a valid final or pending
  branch
- **AND** structured business output remains schema-valid
- **THEN** runtime MAY succeed via soft completion

#### Scenario: waiting fallback remains the last compatibility path
- **WHEN** an interactive attempt resolves neither a valid final nor pending
  branch
- **AND** soft completion does not apply
- **THEN** runtime MAY still enter `waiting_user`
- **AND** it MUST use the default fallback pending payload

