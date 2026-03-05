# job-orchestrator-modularization Specification

## Purpose
TBD - created by archiving change refactor-job-orchestrator-god-object. Update Purpose after archive.
## Requirements
### Requirement: JobOrchestrator MUST act as a coordination layer
The system MUST constrain `JobOrchestrator` to lifecycle coordination and delegation, instead of embedding bundle, filesystem snapshot, audit, interaction lifecycle, and restart recovery implementations in a single class.

#### Scenario: Run execution delegates component responsibilities
- **WHEN** `JobOrchestrator.run_job` processes a run
- **THEN** it MUST delegate bundle, snapshot, audit, and interaction lifecycle operations to dedicated services

#### Scenario: Trust registration canonical path moves with lifecycle
- **WHEN** run-folder trust registration belongs to lifecycle execution
- **THEN** tests MUST assert the lifecycle-service call site
- **AND** the system MUST NOT move the logic back into `JobOrchestrator` only to satisfy legacy tests

### Requirement: Dedicated orchestration services MUST preserve run behavior

The system MUST provide dedicated orchestration services for bundle, filesystem snapshot, audit, interaction lifecycle, restart recovery, and run-folder bootstrap while preserving the existing run behavior and output semantics.

#### Scenario: Create-run materializes the run-local skill snapshot once
- **WHEN** orchestration creates a run from an installed or temporary skill source
- **THEN** the orchestration layer MUST materialize the run-local skill snapshot exactly once
- **AND** later attempts MUST consume that snapshot in place

#### Scenario: Resumed attempt consumes existing snapshot only
- **GIVEN** create-run has already materialized the canonical run-local skill snapshot
- **WHEN** a later resumed attempt is prepared by orchestration services
- **THEN** orchestration MUST continue with the existing snapshot manifest
- **AND** MUST NOT delegate skill installation work to attempt-stage adapter helpers

#### Scenario: Orchestration does not reopen source selection during resume
- **GIVEN** a run-local skill snapshot already exists for the run
- **WHEN** orchestration resolves the skill manifest for a later attempt
- **THEN** orchestration MUST treat the run-local snapshot as the canonical source for that run
- **AND** MUST NOT reopen normal source selection through registry or `skill_override`

### Requirement: Job control integration MUST expose stable bundle API with compatibility fallback
The system MUST expose `build_run_bundle(run_dir, debug)` on job-control integration points and MUST keep compatibility with legacy `_build_run_bundle` callers during migration.

#### Scenario: Runtime read facade can request bundle via stable API
- **WHEN** runtime observability requests a run bundle
- **THEN** it MUST call `build_run_bundle` when available and MUST fall back to `_build_run_bundle` to support legacy implementations

### Requirement: Interactive and recovery semantics MUST remain unchanged
The system MUST keep interactive waiting/reply/auto-decide timeout and restart recovery semantics unchanged after modularization.

#### Scenario: Interactive waiting and auto resume remain consistent
- **WHEN** an interactive run enters `waiting_user` and later receives user reply or timeout auto-decision
- **THEN** status transitions, reply dedup/idempotency behavior, and resume command semantics MUST stay consistent with current behavior

#### Scenario: Restart recovery remains compatible
- **WHEN** orchestrator starts and reconciles incomplete runs
- **THEN** waiting-preserve and failed-reconcile outcomes MUST remain consistent with current statechart-driven behavior

#### Scenario: Lifecycle extraction does not add compatibility shims
- **WHEN** `run_job`, `cancel_run`, or recovery flows execute through lifecycle services
- **THEN** behavior MUST stay compatible with the current public contract
- **AND** the fix MUST land in canonical service code paths
- **AND** the system MUST NOT add legacy wrapper shims to preserve stale tests

### Requirement: Lifecycle execution MUST release admission resources and reconcile orphan queued resumes
The system MUST release runtime admission resources on every post-acquire exit path and MUST reconcile non-runnable queued resume flows through canonical orchestration services.

#### Scenario: run_job releases slot after missing run directory early exit
- **WHEN** `run_job` acquires a concurrency slot and later discovers that `run_dir` is missing
- **THEN** it MUST release the acquired slot exactly once before returning

#### Scenario: queued resume with missing run dir fails reconciliation
- **GIVEN** a queued run has a pending resume ticket
- **AND** its run directory no longer exists
- **WHEN** recovery or observability evaluates whether it can redrive the queued resume
- **THEN** the system MUST NOT redrive the run
- **AND** MUST reconcile the run to `failed`
- **AND** MUST persist `recovery_state=failed_reconciled`

#### Scenario: queued resume with existing run dir redrives normally
- **GIVEN** a queued run has a pending resume ticket
- **AND** its run directory still exists
- **WHEN** recovery or observability redrives the queued resume
- **THEN** the system MAY schedule the resumed attempt
- **AND** MUST preserve existing resume semantics

### Requirement: Live protocol publication MUST precede audit mirroring
The system MUST publish active FCMP/RASP events into live journals before audit mirrors are written, so active delivery does not depend on audit file latency.

#### Scenario: active protocol delivery ignores audit mirror latency
- **WHEN** orchestration or parser emits a live FCMP/RASP event for an active run
- **THEN** the event MUST be published to the live journal first
- **AND** audit append MAY happen asynchronously afterward

### Requirement: Orchestration MUST publish live FCMP state transitions through a shared publisher
The system MUST route orchestration-originated FCMP events through the same live publisher used by parser-originated FCMP events so that active delivery observes a single canonical timeline.

#### Scenario: orchestration state change is visible before audit mirror
- **WHEN** orchestration transitions a run between canonical conversation states
- **THEN** it MUST publish the corresponding FCMP event to the live publisher immediately
- **AND** audit mirroring MAY occur asynchronously afterward

### Requirement: Audit mirrors MUST NOT serve as current truth for active delivery
The system MUST treat audit FCMP/RASP files as history mirrors and MUST NOT require them to exist before active delivery can proceed.

#### Scenario: active delivery ignores audit mirror latency
- **WHEN** a published FCMP or RASP event has not yet been mirrored to disk
- **THEN** SSE and recent history replay MUST still be able to serve the event from live memory

### Requirement: Orchestration-originated lifecycle FCMP MUST flow through the shared ordering publisher
系统 MUST 要求所有 orchestration-originated lifecycle FCMP 通过共享 publisher 进入 canonical FCMP 时间线，禁止 orchestration、observability 或 history 路径绕过 publisher 自行拼装或重排 lifecycle FCMP。

#### Scenario: lifecycle state transition enters the shared FCMP timeline
- **WHEN** orchestration 发布 `conversation.state.changed`、`interaction.reply.accepted`、`auth.completed` 或其他 lifecycle 相关 FCMP
- **THEN** 这些事件 MUST 通过共享 ordering publisher 发布
- **AND** MUST 与 parser-originated FCMP 处于同一 canonical FCMP timeline

### Requirement: Orchestration MUST NOT emit redundant terminal lifecycle FCMP
系统 MUST 不再由 orchestration 额外发布 `conversation.completed` 或 `conversation.failed`，terminal lifecycle 语义 MUST 折叠进 `conversation.state.changed.data.terminal`。

#### Scenario: terminal state uses state.changed only
- **WHEN** orchestration 处理 run terminal
- **THEN** 仅发布 terminal `conversation.state.changed`
- **AND** 不再追加冗余 terminal lifecycle 事件

### Requirement: Result projection MUST respect canonical event gating
系统 MUST 将 final summary、result projection 和其他 terminal-facing 输出视为投影，而不是源事件，并且这些投影 MUST 受 canonical event gating 约束。

#### Scenario: projection cannot outrun waiting state truth
- **GIVEN** orchestration 仍将 run 视为 `waiting_user` 或 `waiting_auth`
- **WHEN** terminal-facing projection 被计算或读取
- **THEN** 系统 MUST NOT 先暴露 terminal projection

#### Scenario: projection cannot outrun terminal causal prerequisites
- **WHEN** orchestration 计算 terminal summary 或 result projection
- **THEN** 它 MUST 先确认对应 canonical terminal lifecycle 前置条件已经满足
- **AND** MUST NOT 因 audit/backfill 已可用而跳过该 gating

### Requirement: Waiting, reply, and resume lifecycle publication MUST preserve causal order
系统 MUST 保证 waiting、reply accepted 与 resumed running 的发布顺序符合因果链，且不得出现 resumed running 早于 reply accepted 已发布的情况。

#### Scenario: resumed running follows reply accepted
- **WHEN** 用户提交合法 reply 并触发 resumed attempt
- **THEN** `interaction.reply.accepted` MUST 先进入 canonical FCMP timeline
- **AND** 对应 resumed attempt 的 `running` MUST 晚于该事件发布

### Requirement: Orchestration MUST gate auth resume on canonical completion only
orchestration MUST 仅根据 canonical auth session terminal success 生成 `auth.completed`、resume ticket 和 `waiting_auth -> queued` 转移。

#### Scenario: readiness-like signal cannot trigger resume
- **WHEN** engine 静态凭据状态已变为可用
- **AND** auth session snapshot 仍为 `waiting_user` 或 `challenge_active`
- **THEN** orchestration MUST NOT issue resume ticket
- **AND** MUST NOT start a new attempt

### Requirement: Waiting-auth reconciliation MUST be idempotent for non-terminal snapshots
系统 MUST 保证 waiting-auth reconcile 在 non-terminal challenge snapshot 上是幂等的。

#### Scenario: repeated reconcile does not advance active challenge
- **WHEN** observability 多次触发 waiting-auth reconcile
- **AND** snapshot 尚未 terminal success
- **THEN** run 状态保持 `waiting_auth`
- **AND** pending auth 保持 challenge-active

### Requirement: Auth orchestrator events MUST use a unified payload contract
系统 MUST 通过统一的 payload contract 写入 auth orchestrator events，避免不同调用点手工拼装出不一致的字段集合。

#### Scenario: auth lifecycle writes stay schema-aligned
- **WHEN** orchestration 写入 auth lifecycle 相关 orchestrator events
- **THEN** 这些 payload MUST 与 `runtime_contract.schema.json` 中声明的字段集合一致
- **AND** `run_audit_service` MUST 继续执行严格校验而不是做隐式兼容修补

#### Scenario: callback accept path does not drift from auth contract
- **WHEN** `run_auth_orchestration_service` 处理 callback/code 提交
- **THEN** 其写出的 `auth.input.accepted` MUST 复用统一 contract
- **AND** 系统 MUST NOT 在不同 auth provider 或提交路径上产生字段命名漂移

### Requirement: opencode auth orchestration MUST derive canonical provider from request model
`opencode` 的 auth orchestration MUST 从 request-side `engine_options.model` 推导 canonical provider，而不是把 detection provider 当作唯一输入。

#### Scenario: canonical provider overrides detection hint for orchestration
- **GIVEN** engine 是 `opencode`
- **AND** request model 解析出的 provider 与 detection hint 不一致或 detection hint 缺失
- **WHEN** orchestration 创建 pending auth
- **THEN** 系统 MUST 以 request model 解析出的 provider 作为 canonical provider

#### Scenario: unresolved model blocks waiting_auth with explicit diagnostic
- **GIVEN** engine 是 `opencode`
- **AND** high-confidence auth detection 已成立
- **AND** request model 无法解析 provider
- **WHEN** orchestration 尝试创建 pending auth
- **THEN** 系统 MUST NOT 静默跳过 waiting_auth
- **AND** 系统 MUST 记录 provider unresolved 的诊断

### Requirement: Orchestration publishes canonical chat replay side effects

When orchestration accepts interaction replies, auth submissions, or emits user-visible system notices, it MUST publish canonical chat replay rows in addition to any FCMP/runtime protocol events.

#### Scenario: Interaction reply emits user chat replay row

- **GIVEN** an interactive reply is accepted
- **WHEN** orchestration persists the reply
- **THEN** a canonical `user` chat replay row is published for that reply

#### Scenario: Auth completion emits system chat replay row

- **GIVEN** auth completes successfully
- **WHEN** orchestration issues the resume path
- **THEN** a canonical `system` chat replay row is published describing the resume notice

### Requirement: interactive reply acceptance MUST 先经过 orchestrator event 再进入 FCMP
系统 MUST 让 interactive reply acceptance 先经过 orchestrator event 管线，再进入 FCMP 发布和下游 chat replay 派生。

#### Scenario: reply submit 先写 orchestrator event 再做 FCMP translation
- **WHEN** 一条 waiting interaction 的 reply 提交成功
- **THEN** orchestration 层 MUST 先追加 `interaction.reply.accepted` orchestrator event
- **AND** 下游 FCMP 发布 MUST 从该 orchestrator event 派生
- **AND** 系统 MUST NOT 直接在 reply endpoint 中发布 FCMP 绕过 orchestrator event path

### Requirement: run_job attempt lifecycle MUST manage run-scoped service log mirroring

`run_job` 在 attempt 执行期间 MUST 绑定 run logging 上下文并启用双镜像会话（run-scope 全集 + attempt-scope 分片），确保并发 run 日志不互串且资源正确释放。

#### Scenario: attempt execution opens and closes mirror session
- **WHEN** `run_job` 解析出 `run_id` 与 `attempt_number` 后进入 attempt 执行
- **THEN** 系统 MUST 开启 run-scope 与 attempt-scope 服务日志镜像会话
- **AND** 在 attempt 任意退出路径（success/failure/cancel/exception）MUST 关闭会话并卸载 handler

#### Scenario: mirror writes only records bound to the target run
- **GIVEN** 多个 run 并发执行
- **WHEN** 服务进程产生日志
- **THEN** 每个 run 的 `service.run.log` MUST 只包含自身 `run_id` 的记录
- **AND** 每个 attempt 的 `service.<attempt>.log` MUST 只包含自身 `run_id + attempt` 的记录
- **AND** 缺少 `run_id` 的记录 MUST 被丢弃

### Requirement: run lifecycle orchestration MUST mirror service logs outside attempt windows

create-run、upload-run、reply/auth 提交与 auth 状态轮询等 attempt 外编排路径 MUST 进入 run-scope 镜像，确保 run 全生命周期日志完整。

#### Scenario: create-run orchestration contributes to run-scope service log
- **WHEN** run 在 router/orchestration 路径被创建并完成 bootstrap/dispatch 准备
- **THEN** 这些服务日志 MUST 写入 `.audit/service.run.log`
- **AND** 这些记录 MAY 不出现在任何 `service.<attempt>.log`

### Requirement: Concurrency Policy Must Be YACS-Managed

Runtime concurrency admission MUST read canonical policy values from system configuration (`config.SYSTEM.CONCURRENCY.*`) rather than a standalone JSON file.

#### Scenario: concurrency manager boots with YACS policy

- **WHEN** runtime starts concurrency manager
- **THEN** it reads max queue and concurrency budget from YACS
- **AND** environment overrides MAY refine those values

### Requirement: Runtime Contract Resolution Must Prefer Canonical Contract Paths

Runtime protocol/schema consumers MUST resolve schemas from canonical contract paths first and only use legacy paths as phase migration fallback.

#### Scenario: schema file exists in canonical path

- **WHEN** protocol schema registry loads runtime contract schema
- **THEN** canonical `server/contracts/schemas/*` is used
- **AND** legacy path is not required

### Requirement: Request persistence MUST be DB-only

Orchestration MUST persist request lifecycle in database storage and MUST NOT rely on request filesystem directories as canonical request state.

#### Scenario: request data persisted without request dir
- **WHEN** a request is created
- **THEN** request metadata MUST be stored in unified request DB model
- **AND** no request directory is required for canonical persistence

### Requirement: Upload staging MUST be request-scoped temporary storage

Orchestration MUST stage uploads in request-local temporary storage during upload handling, then decide cache hit/miss before writing to run directory.

#### Scenario: cache hit discards temporary staging
- **WHEN** upload is processed and cache hits
- **THEN** system MUST bind cached run
- **AND** system MUST discard temporary staging without creating run uploads directory

#### Scenario: cache miss promotes staging to run directory
- **WHEN** upload is processed and cache misses
- **THEN** system MUST create run directory
- **AND** system MUST promote staged uploads into run directory

### Requirement: Runtime chain MUST not branch by temp request identity

Orchestration MUST execute interaction/auth/resume lifecycle from unified request identity and MUST NOT require temp-request-specific branching.

#### Scenario: resume scheduling without temp_request_id branch
- **WHEN** system schedules resumed attempt
- **THEN** orchestration MUST use unified request record only
- **AND** MUST NOT depend on temp request store lookup

### Requirement: Run bundle candidate filtering MUST be rule-file driven

系统 MUST 使用独立规则文件管理 run bundle 的候选文件过滤，而不是在代码中硬编码散落规则。

#### Scenario: non-debug bundle uses allowlist file
- **WHEN** orchestration 构建 `debug=false` 的 run bundle
- **THEN** 系统 MUST 使用非 debug 白名单规则文件筛选候选文件
- **AND** 首版白名单行为 MUST 与当前语义等价（`result/result.json` 与 `artifacts/**`）

#### Scenario: debug bundle uses denylist file
- **WHEN** orchestration 构建 `debug=true` 的 run bundle
- **THEN** 系统 MUST 使用 debug 黑名单规则文件排除候选文件
- **AND** 命中任意层级 `node_modules` 的目录与文件 MUST 被排除

### Requirement: Run explorer filtering MUST reuse debug denylist contract

run 文件树和文件预览 MUST 复用 debug 黑名单规则文件，保持“打包可见集合”与“浏览可见集合”一致。

#### Scenario: filtered paths are hidden from run explorer
- **WHEN** 客户端读取 run 文件树
- **THEN** 命中 debug 黑名单规则的目录与文件 MUST NOT 出现在 entries 中

#### Scenario: filtered file preview is rejected
- **WHEN** 客户端请求 run 文件预览且路径命中 debug 黑名单规则
- **THEN** 系统 MUST 拒绝该预览请求
- **AND** MUST NOT 通过手工路径输入绕过过滤

### Requirement: Orchestration MUST emit request-scoped structured trace events

Runtime orchestration MUST emit stable structured trace logs for upload, lifecycle, interaction/auth, and recovery critical transitions. Critical transitions MUST carry `request_id` and stable event code semantics.

#### Scenario: upload failure can be traced by request_id
- **WHEN** `POST /v1/jobs/{request_id}/upload` fails at any critical phase
- **THEN** backend MUST emit `upload.failed`
- **AND** the event MUST include `request_id`, `phase`, `outcome=error`, and normalized error metadata

#### Scenario: run lifecycle slot handling remains traceable
- **WHEN** orchestration acquires and later releases a runtime slot
- **THEN** backend MUST emit `run.lifecycle.slot_acquired` and `run.lifecycle.slot_released`
- **AND** both events MUST be attributable to the same `run_id`

### Requirement: Recovery redrive decisions MUST be traceable

Recovery service MUST emit structured trace events for resume redrive decisions and orphan reconciliation.

#### Scenario: missing run_dir redrive is reconciled with trace
- **WHEN** queued redrive finds missing run directory
- **THEN** backend MUST emit a reconciliation trace event
- **AND** the event MUST carry `request_id`, `run_id`, and a stable error code for missing runtime assets

