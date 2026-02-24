## Overview

本设计把 session 运行时收敛到单一可恢复范式，并以 Statechart 作为实现与协议的统一约束。

核心目标：

1. 删除 sticky 专属控制面（字段、错误码、watchdog、process binding）。
2. 统一 interactive 回复与自动决策回流路径（`waiting_user -> queued`）。
3. 将 `auto` 保持在同一状态机范式内（策略子集而非独立状态机）。

## State Model

Canonical states:

- `queued`
- `running`
- `waiting_user`
- `succeeded`
- `failed`
- `canceled`

Canonical events:

- `turn.started`
- `turn.needs_input`
- `interaction.reply.accepted`
- `interaction.auto_decide.timeout`
- `turn.succeeded`
- `turn.failed`
- `run.canceled`
- `restart.preserve_waiting`
- `restart.reconcile_failed`

Guard rules:

- `interactive_require_user_reply=false` 才允许触发自动决策超时路径。
- `pending + handle` 同时有效才允许重启后保持 `waiting_user`。

## Runtime Flow

### 1) Waiting and Resume

- 进入 `waiting_user` 时持久化 pending + session handle。
- 用户 reply 被接受后，统一设置 run 为 `queued` 并重新调度下一回合。
- 自动决策（strict=false）同样走 reply 语义并回到 `queued`。

### 2) Timeout

- `session_timeout_sec` 是唯一会话超时参数。
- `strict=true`：超时仅用于等待观察，不触发失败。
- `strict=false`：超时触发自动决策并继续执行。

### 3) Startup Recovery

- `waiting_user`：
  - pending + handle 有效 => 保持 `waiting_user`
  - 否则 => `failed` (`SESSION_RESUME_FAILED`)
- `queued/running`：
  - 收敛 `failed` (`ORCHESTRATOR_RESTART_INTERRUPTED`)

## Storage and Migration

`request_interactive_runtime` 最小化字段：

- `request_id`
- `effective_session_timeout_sec`
- `session_handle_json`
- `updated_at`

迁移策略：

- 启动时一次性迁移旧表到新表（幂等）。
- 旧字段 `profile_json`、`wait_deadline_at`、`process_binding_json` 被删除。

## API and Error Surface

- 移除 `interactive_profile.kind` 对外暴露。
- 移除错误码：
  - `INTERACTION_WAIT_TIMEOUT`
  - `INTERACTION_PROCESS_LOST`
- 保留：
  - `SESSION_RESUME_FAILED`
  - `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
  - `ORCHESTRATOR_RESTART_INTERRUPTED`

## Verification Strategy

1. 结构契约测试：
- `test_session_statechart_contract.py` 校验转换唯一性、可达性、终态约束。

2. 协议对齐测试：
- `test_protocol_state_alignment.py` 校验 RASP/FCMP 关键事件与状态转换一致。

3. 行为回归：
- interactive ask/reply/resume 闭环；
- strict=true 不超时失败；
- strict=false 自动决策继续；
- startup recovery 仅保留 handle+pending 有效性分流。
