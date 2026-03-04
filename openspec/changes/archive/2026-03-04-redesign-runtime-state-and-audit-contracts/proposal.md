# Proposal: Redesign Runtime State And Audit Contracts

## Why

当前 runtime 的状态文件和审计文件长期处于多写者并行维护的状态，已经出现以下系统性问题：

- `status.json`、`current/projection.json`、`pending*.json`、`result/result.json`、`.audit/*` 之间会出现多个“当前真相”
- create-run 到 attempt 1 真正启动之间缺少 durable dispatch truth，导致 `queued` 可能没有完整状态文件
- observability 和 UI 会从 stale `result/result.json` 或缺失审计日志中错误推断当前状态
- waiting payload 与 terminal result 没有明确分层，造成 waiting / queued / running / terminal 语义互相污染

## What Changes

本 change 将 runtime 合同重构为三层状态模型和一层历史模型：

1. `.state/state.json`
   - 唯一 current truth
   - 覆盖当前 run 状态、pending owner、resume 信息、运行策略有效值
2. `.state/dispatch.json`
   - 唯一 dispatch truth
   - 覆盖 `created -> admitted -> dispatch_scheduled -> worker_claimed -> attempt_materializing`
3. `result/result.json`
   - terminal-only
   - 只允许 `succeeded | failed | canceled`
4. `.audit/*`
   - attempt-scoped, append-only, history-only

同时引入 single writer 约束：

- 状态文件只允许由 `run_state_service` 写
- 审计骨架只允许由 `run_audit_contract_service` 初始化
- 业务组件不再直接写 `status.json` / `pending*.json` / `result/result.json`

## Impact

- 新增 OpenSpec specs：
  - `session-runtime-lifecycle`
  - `run-state-contract`
  - `run-audit-contract`
  - `runtime-dispatch-lifecycle`
- 更新 SSOT：
  - `docs/contracts/session_fcmp_invariants.yaml`
  - `docs/run_artifacts.md`
  - `docs/session_runtime_statechart_ssot.md`
  - `docs/session_event_flow_sequence_fcmp.md`
  - `docs/runtime_stream_protocol.md`
  - `docs/runtime_event_schema_contract.md`
- 更新实现：
  - router / lifecycle / auth / interaction / recovery / observability 全部改为 `.state/*` 优先
- 更新 API：
  - status/detail 增加 `dispatch_phase`、`dispatch_ticket_id`、`pending_payload`
  - `/result` 非 terminal 返回 `409 terminal result not ready`
