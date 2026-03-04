## Overview

本 change 将 auth 相关语义拆成两类：

1. `credential_state`
   - engine 静态凭据可观测状态
   - 仅用于 management / observability
   - 不参与 waiting_auth completion、resume、FCMP `auth.completed`
2. canonical auth completion
   - 仅由 auth session terminal success 或显式 callback/submission completion 产生
   - 是 `auth.completed`、`waiting_auth -> queued`、resume ticket issuance 的唯一来源

## Decisions

### 1. `auth_ready` is retired everywhere

- 主实现、主规格、主文档、主测试中不再出现 `auth_ready`
- 不保留 public compatibility alias
- archived changes 中历史文字可保留，但不再作为当前 SSOT

### 2. Waiting-auth reconciliation is completion-only

- `reconcile_waiting_auth()` 只能在 session snapshot terminal success 时推进
- `waiting_user` / `challenge_active` + `credential_state=present` 仍必须保持 `waiting_auth`
- observability 的 repeated polling 必须是 idempotent

### 3. Engine static auth observability and runtime auth completion are decoupled

- `AgentCliManager.collect_auth_status()` 改为返回 `credential_state`
- runtime auth session snapshot 不再暴露 `auth_ready`
- engine-specific runtime handlers 不再通过 readiness 推断 session succeeded

### 4. Single-method busy recovery remains challenge-only

- 单方式 busy recovery 只能恢复或重投影现有 challenge
- busy 不得产生 `auth.completed`
- busy 不得发 resume ticket
- busy 不得离开 `waiting_auth`

### 5. FCMP completion gating follows canonical auth completion

- `auth.completed` 只能来自 canonical auth completion
- `auth.session.busy` / `auth.challenge.updated` / diagnostic.warning / `credential_state` 都不得解锁 `auth.completed`

## Implementation Shape

### SSOT / docs / specs

- `docs/contracts/session_fcmp_invariants.yaml`
- `docs/contracts/runtime_event_ordering_contract.yaml`
- `docs/session_runtime_statechart_ssot.md`
- `docs/session_event_flow_sequence_fcmp.md`
- `docs/runtime_stream_protocol.md`
- `docs/runtime_event_schema_contract.md`
- `docs/api_reference.md`
- main OpenSpec specs:
  - `interactive-job-api`
  - `job-orchestrator-modularization`
  - `engine-adapter-runtime-contract`
  - `engine-auth-observability`
  - `runtime-event-ordering-contract`

### Runtime / orchestration

- `EngineAuthFlowManager`
  - 删除 `_AuthSession.auth_ready`
  - 删除 `_collect_auth_ready()`
  - snapshot / log payload 不再写 `auth_ready`
- `session_lifecycle`
  - 删除 readiness 驱动 success 的逻辑
  - 仅 terminal success 才能完成 session
- `RunAuthOrchestrationService`
  - `_snapshot_completed()` 收窄为 terminal-success 判定
  - waiting_auth reconcile 对 non-terminal snapshot 必须 no-op
- `event_protocol` / `live_publish`
  - `auth.completed` 只接受 canonical completion source

### Engine management

- `AgentCliManager.collect_auth_status()`
  - `auth_ready` -> `credential_state`
- `server/models/engine.py`
  - engine auth 相关 model 同步去掉 `auth_ready`

## Failure Modes Covered

- challenge 出现后未经用户操作自动 resume
- waiting_auth detail/list 轮询触发循环 restart
- 单方式 busy recovery 被误判成 completion
- static credential state 被错误翻译成 `auth.completed`
