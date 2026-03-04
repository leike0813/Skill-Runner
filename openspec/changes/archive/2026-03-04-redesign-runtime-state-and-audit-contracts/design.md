# Design: Runtime State And Audit Contracts

## 1. Core Layers

### 1.1 Current State

唯一 current truth:

- `.state/state.json`

负责：

- `status`
- `current_attempt`
- `pending.owner`
- `pending.payload`
- `resume.*`
- `runtime.*`
- `warnings` / `error`

### 1.2 Dispatch State

唯一 dispatch truth:

- `.state/dispatch.json`

负责：

- `dispatch_ticket_id`
- `phase`
- `worker_claim_id`
- `admitted_at`
- `scheduled_at`
- `claimed_at`
- `last_error`

### 1.3 Terminal Result

唯一 terminal truth:

- `result/result.json`

只允许：

- `succeeded`
- `failed`
- `canceled`

### 1.4 Audit History

attempt-scoped, append-only:

- `.audit/meta.<attempt>.json`
- `.audit/orchestrator_events.<attempt>.jsonl`
- `.audit/events.<attempt>.jsonl`
- `.audit/fcmp_events.<attempt>.jsonl`
- `.audit/stdout.<attempt>.log`
- `.audit/stderr.<attempt>.log`
- `.audit/pty-output.<attempt>.log`
- `.audit/parser_diagnostics.<attempt>.jsonl`
- `.audit/protocol_metrics.<attempt>.json`

## 2. Dispatch Lifecycle

dispatch lifecycle 是 `queued` 的内部 phase：

1. `created`
2. `admitted`
3. `dispatch_scheduled`
4. `worker_claimed`
5. `attempt_materializing`

只有在：

- dispatch claimed
- attempt audit skeleton initialized

之后，才允许：

- `turn.started`
- `status=running`

## 3. Waiting Payload Model

waiting payload 不再独立落盘到 `interactions/pending*.json` 作为 canonical 文件。

统一嵌入：

- `.state/state.json.pending`

其中：

- `waiting_user` -> `pending.owner = waiting_user`
- `waiting_auth.method_selection` -> `pending.owner = waiting_auth.method_selection`
- `waiting_auth.challenge_active` -> `pending.owner = waiting_auth.challenge_active`

## 4. Single Writer Boundary

### 4.1 State Writer

`run_state_service` 是唯一允许写以下文件的组件：

- `.state/state.json`
- `.state/dispatch.json`
- `result/result.json`

### 4.2 Audit Writer

`run_audit_contract_service` 是唯一允许初始化 attempt 审计骨架的组件。

### 4.3 Forbidden Direct Writes

以下组件不得直接写核心状态文件：

- `jobs.py`
- `temp_skill_runs.py`
- `job_orchestrator.py`
- `run_job_lifecycle_service.py`
- `run_auth_orchestration_service.py`
- `run_interaction_service.py`
- `run_interaction_lifecycle_service.py`
- `run_recovery_service.py`
- `run_observability.py`

## 5. Read Priority

所有 read path 必须遵循：

1. `.state/state.json`
2. `.state/dispatch.json`
3. `.audit/*`
4. `result/result.json`

其中：

- waiting/running/queued 绝不从 `result/result.json` 推断
- parser diagnostics 绝不作为状态权威

## 6. Compatibility

为降低迁移风险，短期保留 legacy mirror：

- `status.json`
- `current/projection.json`
- `interactions/pending*.json`

但它们降级为 compatibility outputs，不再是 canonical write target。
