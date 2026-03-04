# Run Artifacts Contract

本文档定义 `data/runs/<run_id>/` 下的 canonical 文件合同。

## 1. 目录结构

```text
data/runs/<run_id>/
├── .state/
│   ├── state.json
│   └── dispatch.json
├── .audit/
│   ├── request_input.json
│   ├── meta.<attempt>.json
│   ├── orchestrator_events.<attempt>.jsonl
│   ├── events.<attempt>.jsonl
│   ├── fcmp_events.<attempt>.jsonl
│   ├── stdin.<attempt>.log
│   ├── stdout.<attempt>.log
│   ├── stderr.<attempt>.log
│   ├── pty-output.<attempt>.log
│   ├── fs-before.<attempt>.json
│   ├── fs-after.<attempt>.json
│   ├── fs-diff.<attempt>.json
│   ├── parser_diagnostics.<attempt>.jsonl
│   └── protocol_metrics.<attempt>.json
├── result/
│   └── result.json
├── artifacts/
├── bundle/
├── uploads/
└── .<engine>/skills/<skill_id>/...
```

## 2. 状态文件

### 2.1 `.state/state.json`

唯一 current truth。

职责：

- 当前 `status`
- 当前 `current_attempt`
- 当前 waiting owner / waiting payload
- 当前 resume ownership
- 当前有效 runtime policy
- 当前 error / warnings

它是以下场景的唯一权威来源：

- `queued`
- `running`
- `waiting_user`
- `waiting_auth`
- terminal 前的全部 current state

### 2.2 `.state/dispatch.json`

唯一 dispatch truth。

职责：

- `dispatch_ticket_id`
- `phase`
- `worker_claim_id`
- `admitted_at`
- `scheduled_at`
- `claimed_at`
- `last_error`

dispatch phase 只允许：

- `created`
- `admitted`
- `dispatch_scheduled`
- `worker_claimed`
- `attempt_materializing`

### 2.3 `result/result.json`

唯一 terminal truth。

只允许在以下状态存在：

- `succeeded`
- `failed`
- `canceled`

该文件不再承担任何 waiting / running / queued 状态表达职责。

## 3. 审计文件

`.audit/*` 全部是：

- attempt-scoped
- append-only
- history-only
- non-authoritative for current state

### 3.1 `meta.<attempt>.json`

attempt 级摘要与上下文：

- `request_id`
- `run_id`
- `attempt_number`
- `status`
- `engine`
- `skill_id`
- 其他 attempt 元信息

### 3.2 `orchestrator_events.<attempt>.jsonl`

编排器内部语义事件历史。

### 3.3 `events.<attempt>.jsonl`

RASP/raw runtime 事件历史。

### 3.4 `fcmp_events.<attempt>.jsonl`

对外 FCMP 事件流的持久化切片。

### 3.5 `stdout.<attempt>.log` / `stderr.<attempt>.log` / `pty-output.<attempt>.log`

attempt 级原始执行输出。

### 3.6 `parser_diagnostics.<attempt>.jsonl`

parser/materialization diagnostics。

注意：

- diagnostics 只用于排查和观测
- diagnostics 不是当前状态权威

### 3.7 `protocol_metrics.<attempt>.json`

协议物化统计，例如：

- `event_count`
- `diagnostic_count`
- `parser_warning_count`

## 4. 输入与运行资产

### 4.1 `.audit/request_input.json`

记录 run 创建时的请求输入快照，用于审计、回放和 bundle。

该文件不再作为 runtime 关键执行数据读取入口。

### 4.2 `.<engine>/skills/<skill_id>/...`

run-local skill snapshot。

普通 skill 与 temp skill 都在 create-run 阶段物化到 run 目录，后续所有 attempt / resume 都只从该快照加载。
temp skill 的上传 zip 不再作为持久运行资产保留，也不再存在 staging 目录参与 resumed attempt 恢复。

### 4.3 `artifacts/`

run 产出的文件型成果。

### 4.4 `bundle/`

可下载的 run bundle 及 manifest。

## 5. Single Writer 约束

### 5.1 `run_state_service`

唯一允许写：

- `.state/state.json`
- `.state/dispatch.json`
- `result/result.json`

### 5.2 `run_audit_contract_service`

唯一允许初始化：

- `.audit/meta.<attempt>.json`
- `.audit/stdout.<attempt>.log`
- `.audit/stderr.<attempt>.log`
- 其他 attempt 审计骨架

## 6. Legacy 文件

以下文件降级为 legacy，不再作为 canonical contract：

- `status.json`
- `current/projection.json`
- `interactions/pending.json`
- `interactions/pending_auth.json`
- `interactions/pending_auth_method_selection.json`
- `interactions/history.jsonl`
- `interactions/runtime_state.json`
- `logs/prompt.txt`
- `logs/stdout.txt`
- `logs/stderr.txt`
- `raw/output.json`
- `input.json`

新 run 不得继续写入这些文件。
